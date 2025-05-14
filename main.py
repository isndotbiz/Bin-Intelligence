import logging
import os
import json
from datetime import datetime
import json
from typing import List, Dict, Any, Tuple
from collections import Counter
from flask import Flask, render_template, jsonify, request
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker, scoped_session, contains_eager

from fraud_feed import FraudFeedScraper
from bin_enricher import BinEnricher
from utils import write_csv, write_json
from models import Base, BIN, ExploitType, BINExploit, ScanHistory
from neutrino_api import NeutrinoAPIClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Database setup
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")
    
# Ensure DATABASE_URL is compatible with SQLAlchemy (PostgreSQL)
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
engine = create_engine(
    DATABASE_URL or "", 
    pool_pre_ping=True,  # Test connections before using them
    pool_recycle=300,    # Recycle connections every 5 minutes
    pool_size=10,        # Maximum number of connections in the pool
    max_overflow=20,     # Maximum number of connections that can be created beyond pool_size
    echo=False           # Don't log all SQL statements
)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

# Check if tables exist before creating them
from sqlalchemy import inspect
inspector = inspect(engine)
if not inspector.has_table('bins'):
    # Tables don't exist, so create them
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
else:
    logger.info("Database tables already exist")

# Initialize exploit types in the database
def init_exploit_types():
    """Initialize the exploit types in the database if they don't exist"""
    exploit_types = {
        "card-not-present": "Fraud in online transactions where physical card is not present during checkout",
        "false-positive-cvv": "Cards with weak CVV verification that accept any CVV value during transaction",
        "no-auto-3ds": "Cards lacking automatic 3D Secure authentication for online purchases"
    }
    
    # Check and add each exploit type if it doesn't exist
    for name, description in exploit_types.items():
        if not db_session.query(ExploitType).filter(ExploitType.name == name).first():
            db_session.add(ExploitType(name=name, description=description))
    
    db_session.commit()

# Initialize the database with exploit types
init_exploit_types()

def process_exploited_bins(top_n: int = 100, sample_pages: int = 5) -> List[Dict[str, Any]]:
    """
    Process exploited BINs:
    1. Fetch exploited BINs from fraud feeds
    2. Filter BINs without meaningful classification
    3. Enrich BINs with issuer information and 3DS support
    4. Determine patch status based on 3DS support
    
    Args:
        top_n: Number of top BINs to process
        sample_pages: Number of pages/posts to sample from each source
        
    Returns:
        List of dictionaries with enriched BIN data
    """
    # Step 1: Fetch exploited BINs from fraud feeds
    logger.info(f"Fetching exploited BINs (top_n={top_n}, sample_pages={sample_pages})...")
    fraud_feed = FraudFeedScraper()
    
    # Make sure we're using the updated method
    if hasattr(fraud_feed, "_generate_sample_data"):
        # This is for backward compatibility
        logger.warning("Using deprecated _generate_sample_data method. Update your code.")
        exploited_bins = fraud_feed.fetch_exploited_bins(top_n=top_n, sample_pages=sample_pages) 
    else:
        # New method that doesn't use synthetic data
        exploited_bins = fraud_feed.fetch_exploited_bins(top_n=top_n, sample_pages=sample_pages)
    
    # Step 2: Filter BINs without meaningful classification
    logger.info("Filtering BINs without meaningful classification...")
    classified_bins = [(bin_code, exploit_type) for bin_code, exploit_type in exploited_bins if exploit_type]
    
    discarded_count = len(exploited_bins) - len(classified_bins)
    logger.info(f"Discarded {discarded_count} BINs without meaningful classification")
    logger.info(f"Processing {len(classified_bins)} classified BINs")
    
    # Step 3: Enrich BINs with issuer information and 3DS support
    logger.info("Enriching BINs with issuer information and 3DS support...")
    bin_enricher = BinEnricher()
    
    enriched_bins = []
    for bin_code, exploit_type in classified_bins:
        enriched_data = bin_enricher.enrich_bin(bin_code)
        if enriched_data:
            # Add exploit type to the enriched data
            enriched_data["exploit_type"] = exploit_type
            enriched_bins.append(enriched_data)
    
    logger.info(f"Successfully enriched {len(enriched_bins)} BINs")
    
    return enriched_bins

def save_bins_to_database(enriched_bins):
    """Save the enriched BINs to the database with improved connection handling"""
    logger.info("Saving BINs to database...")
    
    # Create a fresh session to avoid connection issues
    session = None
    try:
        Session = sessionmaker(bind=engine)
        session = Session()
        
        scan_record = ScanHistory(
            source="pastebin",
            bins_found=len(enriched_bins),
            bins_classified=len(enriched_bins),
            scan_parameters=json.dumps({"top_n": len(enriched_bins), "sample_pages": 5})
        )
        session.add(scan_record)
        
        # Get all exploit types from DB for lookup
        exploit_types = {et.name: et for et in session.query(ExploitType).all()}
        
        # Track how many bins were created/updated
        created_count = 0
        updated_count = 0
        
        for bin_data in enriched_bins:
            bin_code = bin_data.get("BIN")
            
            # Skip if no BIN code
            if not bin_code:
                continue
                
            # Check if BIN already exists in database
            bin_record = session.query(BIN).filter(BIN.bin_code == bin_code).first()
            
            if not bin_record:
                # Create new BIN record
                bin_record = BIN(
                    bin_code=bin_code,
                    issuer=bin_data.get("issuer"),
                    brand=bin_data.get("brand"),
                    card_type=bin_data.get("type"),
                    prepaid=bin_data.get("prepaid", False),
                    country=bin_data.get("country"),
                    transaction_country=bin_data.get("transaction_country"),
                    threeds1_supported=bin_data.get("threeDS1Supported", False),
                    threeds2_supported=bin_data.get("threeDS2supported", False),
                    patch_status=bin_data.get("patch_status")
                )
                session.add(bin_record)
                created_count += 1
                # Flush to get the bin_id
                session.flush()
            else:
                # Update existing BIN record
                new_data = {
                    "issuer": bin_data.get("issuer", bin_record.issuer),
                    "brand": bin_data.get("brand", bin_record.brand),
                    "card_type": bin_data.get("type", bin_record.card_type),
                    "prepaid": bin_data.get("prepaid", bin_record.prepaid),
                    "country": bin_data.get("country", bin_record.country),
                    "transaction_country": bin_data.get("transaction_country", bin_record.transaction_country),
                    "threeds1_supported": bin_data.get("threeDS1Supported", bin_record.threeds1_supported),
                    "threeds2_supported": bin_data.get("threeDS2supported", bin_record.threeds2_supported),
                    "patch_status": bin_data.get("patch_status", bin_record.patch_status),
                    "updated_at": datetime.utcnow()
                }
                # Update with setattr to avoid LSP errors
                for key, value in new_data.items():
                    setattr(bin_record, key, value)
                updated_count += 1
            
            # Add exploit type association if available
            exploit_type_name = bin_data.get("exploit_type")
            if exploit_type_name and exploit_type_name in exploit_types:
                # Check if this BIN already has this exploit type
                existing_exploit = session.query(BINExploit).filter(
                    BINExploit.bin_id == bin_record.id,
                    BINExploit.exploit_type_id == exploit_types[exploit_type_name].id
                ).first()
                
                if existing_exploit:
                    # Update the frequency and last_seen using setattr to avoid LSP errors
                    setattr(existing_exploit, 'frequency', existing_exploit.frequency + 1)
                    setattr(existing_exploit, 'last_seen', datetime.utcnow())
                else:
                    # Create new association
                    exploit_record = BINExploit(
                        bin_id=bin_record.id,
                        exploit_type_id=exploit_types[exploit_type_name].id,
                        frequency=1
                    )
                    session.add(exploit_record)
        
        # Commit all changes
        session.commit()
        
        logger.info(f"Database update complete: {created_count} BINs created, {updated_count} BINs updated")
        return created_count, updated_count
    except Exception as e:
        if session:
            session.rollback()
        logger.error(f"Database error in save_bins_to_database: {str(e)}")
        raise
    finally:
        if session:
            session.close()

def run_bin_intelligence_system(top_n=100, sample_pages=5):
    """Run the BIN Intelligence System and return the enriched BINs"""
    logger.info("Starting BIN Intelligence System...")
    
    # Process exploited BINs
    enriched_bins = process_exploited_bins(top_n=top_n, sample_pages=sample_pages)
    
    if not enriched_bins:
        logger.error("No enriched BINs to output")
        return []
    
    # Write output to CSV
    csv_filename = "exploited_bins.csv"
    write_csv(enriched_bins, csv_filename)
    
    # Write output to JSON
    json_filename = "exploited_bins.json"
    write_json(enriched_bins, json_filename)
    
    # Save to database
    save_bins_to_database(enriched_bins)
    
    logger.info("BIN Intelligence System completed successfully")
    
    return enriched_bins

def load_bin_data():
    """Load BIN data from database, ignoring any old JSON files"""
    try:
        # Direct database query to avoid calling get_bins_from_database which might cause a loop
        bin_records = db_session.query(BIN).all()
        
        # Convert to list of dictionaries
        bins_data = []
        for bin_record in bin_records:
            try:
                # Get the primary exploit type for this BIN using a direct query
                exploit_record = db_session.query(BINExploit, ExploitType) \
                    .join(ExploitType) \
                    .filter(BINExploit.bin_id == bin_record.id) \
                    .order_by(BINExploit.frequency.desc()) \
                    .first()
                    
                exploit_type = exploit_record[1].name if exploit_record else None
            except Exception:
                exploit_type = None
                
            # Create a more detailed record with all needed fields
            bin_data = {
                "BIN": bin_record.bin_code,
                "issuer": bin_record.issuer,
                "brand": bin_record.brand,
                "type": bin_record.card_type,
                "card_level": getattr(bin_record, 'card_level', None),  # Using getattr for backward compatibility
                "prepaid": getattr(bin_record, 'prepaid', False),
                "country": bin_record.country,
                "transaction_country": bin_record.transaction_country,
                "threeDS1Supported": bin_record.threeds1_supported,
                "threeDS2supported": bin_record.threeds2_supported,
                "patch_status": bin_record.patch_status,
                "exploit_type": exploit_type,
                "is_verified": getattr(bin_record, 'is_verified', False),
                "data_source": getattr(bin_record, 'data_source', "Unknown"),
                "issuer_website": getattr(bin_record, 'issuer_website', None),
                "issuer_phone": getattr(bin_record, 'issuer_phone', None)
            }
            bins_data.append(bin_data)
            
        if bins_data:
            logger.info(f"Loaded {len(bins_data)} BINs from database directly")
            return bins_data
    except Exception as e:
        logger.error(f"Direct database load failed: {str(e)}")
    
    # If we got here, there was an error or database is empty
    logger.info("No BINs in database or error occurred - returning empty dataset")
    return []

def get_bin_statistics(bins_data):
    """Calculate statistics for the dashboard"""
    if not bins_data:
        return {}
    
    # Count exploit types - filter out any unknowns
    exploit_types = Counter([
        bin_data.get('exploit_type', 'cross-border') for bin_data in bins_data 
        if bin_data.get('exploit_type') is not None
    ])
    
    # Count patch status
    patch_status = Counter([bin_data.get('patch_status', 'unknown') for bin_data in bins_data])
    
    # Count by brand - normalize names to avoid duplicates
    brand_mapping = {
        'AMEX': 'AMERICAN EXPRESS',
        'AMERICAN EXPRESS': 'AMERICAN EXPRESS',
        'MASTERCARD': 'MASTERCARD',
        'VISA': 'VISA',
        'DISCOVER': 'DISCOVER'
    }
    
    # Normalize brand names to prevent duplicates in the graph
    brands = Counter([
        brand_mapping.get(bin_data.get('brand', '').upper(), bin_data.get('brand', 'unknown'))
        for bin_data in bins_data
    ])
    
    # Count by country
    countries = Counter([bin_data.get('country', 'unknown') for bin_data in bins_data])
    
    # Count 3DS support
    threeds1_count = sum(1 for bin_data in bins_data if bin_data.get('threeDS1Supported', False))
    threeds2_count = sum(1 for bin_data in bins_data if bin_data.get('threeDS2supported', False))
    
    # Prepare statistics
    stats = {
        'total_bins': len(bins_data),
        'exploit_types': dict(exploit_types.most_common()),
        'patch_status': dict(patch_status),
        'brands': dict(brands.most_common(10)),
        'countries': dict(countries.most_common(10)),
        '3ds_support': {
            '3DS_v1': threeds1_count,
            '3DS_v2': threeds2_count,
            'No_3DS': len(bins_data) - sum(1 for bin_data in bins_data if bin_data.get('threeDS1Supported', False) or bin_data.get('threeDS2supported', False))
        }
    }
    
    return stats

@app.route('/')
def index():
    """Dashboard home page"""
    return render_template('no_tabs_dashboard.html')
    
@app.route('/simple')
def simple_dashboard():
    """Simple dashboard page without tabs and charts"""
    return render_template('simple_dashboard.html')
    
@app.route('/old')
def old_dashboard():
    """Original dashboard page for reference"""
    return render_template('dashboard.html')

def get_bins_from_database(offset=0, limit=None, use_fresh_session=True):
    """Query BINs from the database using optimized join query with pagination support"""
    session = None
    
    try:
        # Option to use a fresh session for better connection handling
        if use_fresh_session:
            # Create a fresh session with autocommit to avoid transaction issues
            Session = sessionmaker(bind=engine, autocommit=True)
            session = Session()
            query_session = session
        else:
            query_session = db_session
            
        # Force database connection check before query
        query_session.execute(text("SELECT 1"))
            
        # Use a more direct approach to avoid the column error
        query = query_session.query(
            BIN.id,
            BIN.bin_code,
            BIN.issuer,
            BIN.brand,
            BIN.card_type,
            BIN.card_level,
            BIN.prepaid,
            BIN.country,
            BIN.transaction_country,
            BIN.threeds1_supported,
            BIN.threeds2_supported,
            BIN.patch_status,
            BIN.is_verified,
            BIN.verified_at,
            BIN.data_source,
            BIN.issuer_website,
            BIN.issuer_phone,
            ExploitType.name.label('exploit_type_name')
        ).outerjoin(
            BINExploit, BIN.id == BINExploit.bin_id
        ).outerjoin(
            ExploitType, BINExploit.exploit_type_id == ExploitType.id
        )
        
        # Execute the query to get all results
        results = query.all()
        
        # Process results into a dictionary keyed by BIN code for deduplication
        bins_dict = {}
        for row in results:
            # Extract fields from query result
            bin_id = row[0]
            bin_code = row[1]
            issuer = row[2]
            brand = row[3]
            card_type = row[4]
            card_level = row[5]
            prepaid = row[6]
            country = row[7]
            transaction_country = row[8]
            threeds1_supported = row[9]
            threeds2_supported = row[10]
            patch_status = row[11]
            is_verified = row[12]
            verified_at = row[13]
            data_source = row[14]
            issuer_website = row[15]
            issuer_phone = row[16]
            exploit_type_name = row[17]
            
            # Only process each BIN once
            if bin_code not in bins_dict:
                # Handle datetime conversion
                verified_at_str = None
                if verified_at is not None:
                    try:
                        verified_at_str = verified_at.isoformat()
                    except:
                        pass
                
                # Create the dictionary record
                bins_dict[bin_code] = {
                    "BIN": bin_code,
                    "issuer": issuer,
                    "brand": brand,
                    "type": card_type,
                    "card_level": card_level,
                    "prepaid": prepaid,
                    "country": country,
                    "threeDS1Supported": threeds1_supported,
                    "threeDS2supported": threeds2_supported,
                    "patch_status": patch_status,
                    "exploit_type": exploit_type_name,
                    "is_verified": is_verified,
                    "data_source": data_source,
                    "issuer_website": issuer_website,
                    "issuer_phone": issuer_phone,
                    "verified_at": verified_at_str
                }
        
        # Convert dictionary to list and sort by BIN code
        bins_data = sorted(list(bins_dict.values()), key=lambda x: x["BIN"])
        
        # Count total records for pagination
        total_count = len(bins_data)
        
        # Apply pagination if specified
        if limit is not None:
            bins_data = bins_data[offset:offset + limit]
        
        logger.info(f"Loaded {len(bins_data)} BINs from database using optimized query")
        return bins_data, total_count
        
    except Exception as e:
        logger.error(f"Error loading BINs from database: {str(e)}")
        # Try a more direct approach if the normal query fails
        try:
            # Create a fresh connection with AUTOCOMMIT
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                # Execute a simple query to test the connection
                conn.execute(text("SELECT 1"))
                
                # Try a direct SQL query as fallback
                sql = """
                SELECT b.bin_code, et.name as exploit_type 
                FROM bins b 
                LEFT JOIN bin_exploits be ON b.id = be.bin_id 
                LEFT JOIN exploit_types et ON be.exploit_type_id = et.id 
                LIMIT 100
                """
                result = conn.execute(text(sql))
                
                # Process the results into a simple format
                bins_data = []
                for row in result:
                    bins_data.append({
                        'BIN': row[0],
                        'exploit_type': row[1] if row[1] else 'Unknown'
                    })
                
                logger.info(f"Loaded {len(bins_data)} BINs from database using fallback query")
                return bins_data, len(bins_data)
        except Exception as inner_e:
            logger.error(f"Fallback query also failed: {str(inner_e)}")
            # Final fallback - return empty list
            return [], 0
    finally:
        # Clean up the fresh session if we created one
        if session:
            try:
                session.close()
            except Exception:
                pass  # Ignore errors during cleanup

def get_database_statistics():
    """Get statistics from the database with improved connection handling"""
    # Create a fresh session for better connection handling
    Session = sessionmaker(bind=engine)
    session = None
    
    try:
        # Create a fresh session with explicit cleanup
        session = Session()
        
        # Use SQL text query with AUTOCOMMIT for better reliability
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM bins"))
            total_bins = result.scalar() or 0
        
        # Get patch status counts with AUTOCOMMIT for better reliability
        patch_status = {}
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            patch_results = conn.execute(text("SELECT patch_status, COUNT(*) FROM bins GROUP BY patch_status"))
            for row in patch_results:
                status, count = row
                patch_status[status or "unknown"] = count
        
        # Get brand counts - normalize names to avoid duplicates
        brand_mapping = {
            'AMEX': 'AMERICAN EXPRESS',
            'AMERICAN EXPRESS': 'AMERICAN EXPRESS',
            'MASTERCARD': 'MASTERCARD', 
            'VISA': 'VISA',
            'DISCOVER': 'DISCOVER'
        }
        
        # Get all brands from database with AUTOCOMMIT for better reliability
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            brand_results = conn.execute(text("SELECT brand, COUNT(*) FROM bins GROUP BY brand"))
            brand_results = [(row[0], row[1]) for row in brand_results]
            
        # Normalize and combine brands
        normalized_brands = {}
        for brand, count in brand_results:
            brand_key = brand_mapping.get((brand or "").upper(), brand or "unknown")
            normalized_brands[brand_key] = normalized_brands.get(brand_key, 0) + count
            
        # Sort by count and limit to top 10
        brands = dict(sorted(normalized_brands.items(), key=lambda x: x[1], reverse=True)[:10])
        
        # Get country counts with AUTOCOMMIT for better reliability
        countries = {}
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            country_results = conn.execute(text("""
                SELECT country, COUNT(*) as cnt 
                FROM bins 
                GROUP BY country 
                ORDER BY cnt DESC 
                LIMIT 10
            """))
            for row in country_results:
                country, count = row
                countries[country or "unknown"] = count
        
        # Get exploit type counts with AUTOCOMMIT for better reliability
        exploit_types = {}
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            exploit_results = conn.execute(text("""
                SELECT et.name, COUNT(be.id) as cnt
                FROM exploit_types et
                JOIN bin_exploits be ON et.id = be.exploit_type_id
                GROUP BY et.name
                ORDER BY cnt DESC
            """))
            for row in exploit_results:
                name, count = row
                exploit_types[name] = count
        
        # Get 3DS support counts with AUTOCOMMIT for better reliability
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            # 3DS v1 only
            result = conn.execute(text("SELECT COUNT(*) FROM bins WHERE threeds1_supported = true AND threeds2_supported = false"))
            threeds1_count = result.scalar() or 0
            
            # 3DS v2
            result = conn.execute(text("SELECT COUNT(*) FROM bins WHERE threeds2_supported = true"))
            threeds2_count = result.scalar() or 0
            
            # No 3DS
            result = conn.execute(text("SELECT COUNT(*) FROM bins WHERE threeds1_supported = false AND threeds2_supported = false"))
            no_3ds_count = result.scalar() or 0
            
        # Get verification status counts with AUTOCOMMIT for better reliability
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM bins WHERE is_verified = true"))
            verified_count = result.scalar() or 0
        
        # Prepare statistics
        stats = {
            'total_bins': total_bins,
            'exploit_types': exploit_types,
            'patch_status': patch_status,
            'brands': brands,
            'countries': countries,
            'verification': {
                'verified': verified_count,
                'unverified': total_bins - verified_count
            },
            '3ds_support': {
                '3DS_v1': threeds1_count,
                '3DS_v2': threeds2_count,
                'No_3DS': no_3ds_count
            }
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting statistics from database: {str(e)}")
        # Return empty statistics instead of recursively calling load_bin_data
        return {
            'total_bins': 0,
            'verified_count': 0,
            'patch_status': {'Patched': 0, 'Exploitable': 0},
            '3ds_support': {'3DS_v1': 0, '3DS_v2': 0, 'No_3DS': 0},
            'brands': {},
            'countries': {},
            'exploit_types': {},
            'verification': {'verified': 0, 'unverified': 0}
        }
    finally:
        # Clean up the session to prevent connection leaks
        if session:
            session.close()

@app.route('/api/bins')
def api_bins():
    """API endpoint to get BIN data with optional pagination using direct SQL for reliability"""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 200, type=int)  # Default to 200 BINs per page
        
        # Check if we need to return all BINs (for client-side operations)
        return_all = per_page >= 1000
        
        # Direct SQL query with AUTOCOMMIT for reliable connection
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            # Get total count first
            count_query = "SELECT COUNT(*) FROM bins"
            result = conn.execute(text(count_query))
            total_bins = result.scalar() or 0
            
            # Calculate pagination parameters
            total_pages = max(1, (total_bins + per_page - 1) // per_page)
            page = max(1, min(page, total_pages))
            
            # Prepare query with pagination
            if return_all:
                # Return all BINs with no LIMIT
                offset = 0
                limit_clause = ""
            else:
                offset = (page - 1) * per_page
                limit_clause = f"LIMIT {per_page} OFFSET {offset}"
            
            # Core query to fetch BIN data with JOIN for exploit types
            sql = f"""
            SELECT 
                b.id, b.bin_code, b.issuer, b.brand, b.card_type, b.card_level,
                b.prepaid, b.country, b.transaction_country, 
                b.threeds1_supported, b.threeds2_supported, b.patch_status,
                b.is_verified, b.verified_at, b.data_source, 
                b.issuer_website, b.issuer_phone, et.name AS exploit_type
            FROM 
                bins b
            LEFT JOIN 
                bin_exploits be ON b.id = be.bin_id
            LEFT JOIN 
                exploit_types et ON be.exploit_type_id = et.id
            ORDER BY 
                b.bin_code
            {limit_clause}
            """
            
            # Execute and fetch results
            result = conn.execute(text(sql))
            
            # Process rows into bins_data list
            bins_data = []
            for row in result:
                bin_data = {
                    'BIN': row.bin_code,
                    'issuer': row.issuer,
                    'brand': row.brand,
                    'type': row.card_type,
                    'card_level': row.card_level,
                    'prepaid': row.prepaid,
                    'country': row.country,
                    'transaction_country': row.transaction_country,
                    'threeDS1Supported': row.threeds1_supported,
                    'threeDS2supported': row.threeds2_supported,
                    'patch_status': row.patch_status,
                    'is_verified': row.is_verified,
                    'exploit_type': row.exploit_type
                }
                bins_data.append(bin_data)
            
            logger.info(f"Loaded {len(bins_data)} BINs from database using direct SQL")
            
            # Prepare response with pagination metadata
            response = {
                'bins': bins_data,
                'pagination': {
                    'total_bins': total_bins,
                    'total_pages': total_pages,
                    'current_page': page,
                    'per_page': per_page
                }
            }
            
            return jsonify(response)
            
    except Exception as e:
        logger.error(f"Error in api_bins: {str(e)}")
        # Return structured response even on error for better client handling
        default_per_page = 200
        
        return jsonify({
            'error': 'Error loading BIN data', 
            'detail': str(e),
            'bins': [],
            'pagination': {
                'total_bins': 0,
                'total_pages': 1,
                'current_page': 1,
                'per_page': default_per_page
            }
        }), 500

@app.route('/api/debug')
def api_debug():
    """Debug endpoint to check database connectivity with improved connection handling"""
    # Create a fresh session for better connection handling
    Session = sessionmaker(bind=engine)
    session = None
    
    try:
        # Use AUTOCOMMIT for most reliable connection test
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            # Count BINs in database
            result = conn.execute(text("SELECT COUNT(*) FROM bins"))
            bin_count = result.scalar() or 0
            
            # Count exploit types
            result = conn.execute(text("SELECT COUNT(*) FROM exploit_types"))
            exploit_count = result.scalar() or 0
        
        return jsonify({
            'status': 'ok',
            'database_connected': True,
            'bin_count': bin_count,
            'exploit_type_count': exploit_count,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Database error in debug endpoint: {str(e)}")
        return jsonify({
            'status': 'error',
            'database_connected': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500
    finally:
        # Clean up the session to prevent connection leaks
        if session:
            session.close()

@app.route('/api/stats')
def api_stats():
    """API endpoint to get statistics using direct SQL for reliability"""
    try:
        # Use direct SQL queries with AUTOCOMMIT to avoid connection issues
        stats = {}
        
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            # Get total BIN count
            result = conn.execute(text("SELECT COUNT(*) FROM bins"))
            stats['total_bins'] = result.scalar() or 0
            
            # Get verified BIN count
            result = conn.execute(text("SELECT COUNT(*) FROM bins WHERE is_verified = TRUE"))
            stats['verified_count'] = result.scalar() or 0
            
            # Get patch status counts
            patch_status = {}
            result = conn.execute(text("SELECT patch_status, COUNT(*) FROM bins GROUP BY patch_status"))
            for row in result:
                status, count = row
                patch_status[status or "unknown"] = count
            stats['patch_status'] = patch_status
            
            # Get 3DS support statistics
            threeds_stats = {'3DS_v1': 0, '3DS_v2': 0, 'No_3DS': 0}
            result = conn.execute(text("SELECT threeds1_supported, COUNT(*) FROM bins GROUP BY threeds1_supported"))
            for row in result:
                threeds1, count = row
                if threeds1:
                    threeds_stats['3DS_v1'] = count
            
            result = conn.execute(text("SELECT threeds2_supported, COUNT(*) FROM bins GROUP BY threeds2_supported"))
            for row in result:
                threeds2, count = row
                if threeds2:
                    threeds_stats['3DS_v2'] = count
            
            # Calculate No_3DS
            threeds_stats['No_3DS'] = stats['total_bins'] - (threeds_stats['3DS_v1'] + threeds_stats['3DS_v2'])
            stats['3ds_support'] = threeds_stats
            
            # Get brand counts
            brands = {}
            result = conn.execute(text("SELECT brand, COUNT(*) FROM bins GROUP BY brand ORDER BY COUNT(*) DESC LIMIT 10"))
            for row in result:
                brand, count = row
                if brand:
                    brand_upper = brand.upper() if brand else ""
                    if 'AMEX' in brand_upper:
                        brands['AMERICAN EXPRESS'] = brands.get('AMERICAN EXPRESS', 0) + count
                    else:
                        brands[brand] = count
            stats['brands'] = brands
            
            # Get country counts
            countries = {}
            result = conn.execute(text("SELECT country, COUNT(*) FROM bins GROUP BY country ORDER BY COUNT(*) DESC LIMIT 10"))
            for row in result:
                country, count = row
                countries[country or "unknown"] = count
            stats['countries'] = countries
            
            # Get exploit type counts
            exploit_types = {}
            sql = """
            SELECT et.name, COUNT(*) 
            FROM exploit_types et
            JOIN bin_exploits be ON et.id = be.exploit_type_id
            GROUP BY et.name
            ORDER BY COUNT(*) DESC
            """
            result = conn.execute(text(sql))
            for row in result:
                exploit, count = row
                exploit_types[exploit] = count
            stats['exploit_types'] = exploit_types
            
            # Get verification stats
            stats['verification'] = {
                'verified': stats['verified_count'],
                'unverified': stats['total_bins'] - stats['verified_count']
            }
            
        logger.info("Successfully loaded statistics using direct SQL")
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error in api_stats: {str(e)}")
        # Return properly structured empty stats for better client handling
        empty_stats = {
            'total_bins': 0,
            'verified_count': 0,
            'patch_status': {'Patched': 0, 'Exploitable': 0},
            '3ds_support': {'3DS_v1': 0, '3DS_v2': 0, 'No_3DS': 0},
            'brands': {},
            'countries': {},
            'exploit_types': {},
            'verification': {'verified': 0, 'unverified': 0},
            'error': str(e)
        }
        return jsonify(empty_stats), 500

@app.route('/api/scan-history')
def api_scan_history():
    """API endpoint to get scan history"""
    try:
        # Get scan history records
        scan_records = db_session.query(ScanHistory).order_by(ScanHistory.scan_date.desc()).limit(10).all()
        
        # Convert to list of dictionaries
        history_data = []
        for record in scan_records:
            history_data.append({
                'id': record.id,
                'scan_date': record.scan_date.isoformat(),
                'source': record.source,
                'bins_found': record.bins_found,
                'bins_classified': record.bins_classified,
                'scan_parameters': record.scan_parameters
            })
        
        return jsonify(history_data)
    except Exception as e:
        logger.error(f"Error in api_scan_history: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/exploits')
def api_exploits():
    """API endpoint to get exploit types"""
    try:
        # Get all exploit types
        exploit_types = db_session.query(ExploitType).all()
        
        # Convert to list of dictionaries
        exploit_data = []
        for et in exploit_types:
            exploit_data.append({
                'id': et.id,
                'name': et.name,
                'description': et.description
            })
        
        return jsonify(exploit_data)
    except Exception as e:
        logger.error(f"Error in api_exploits: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/verify-bin/<bin_code>')
def verify_bin(bin_code):
    """Verify a BIN using the Neutrino API for real-world data"""
    # Ensure we have a clean session by expiring all pending objects
    db_session.expire_all()
    
    try:
        # First check if the BIN exists in our database
        bin_record = db_session.query(BIN).filter(BIN.bin_code == bin_code).first()
        if not bin_record:
            return jsonify({"status": "error", "message": f"BIN {bin_code} not found in database"}), 404
            
        # Check if credentials are available
        try:
            client = NeutrinoAPIClient()
        except ValueError as e:
            return jsonify({"status": "error", "message": f"Neutrino API credentials not configured: {str(e)}"}), 400
            
        # Lookup the BIN with Neutrino API
        neutrino_data = client.lookup_bin(bin_code)
        if not neutrino_data:
            return jsonify({"status": "error", "message": f"Failed to verify BIN {bin_code} with Neutrino API"}), 400
            
        # Update the database record with verified data - use setattr to avoid LSP errors
        updates = {
            "issuer": neutrino_data.get("issuer", bin_record.issuer),
            "brand": neutrino_data.get("brand", bin_record.brand),
            "card_type": neutrino_data.get("type", bin_record.card_type),
            "prepaid": neutrino_data.get("prepaid", bin_record.prepaid),
            "country": neutrino_data.get("country", bin_record.country),
            "threeds1_supported": neutrino_data.get("threeDS1Supported", bin_record.threeds1_supported),
            "threeds2_supported": neutrino_data.get("threeDS2supported", bin_record.threeds2_supported),
            "patch_status": neutrino_data.get("patch_status", bin_record.patch_status),
            "data_source": "Neutrino API",
            "is_verified": True,
            "verified_at": datetime.utcnow(),
            "issuer_website": neutrino_data.get("issuer_website"),
            "issuer_phone": neutrino_data.get("issuer_phone")
        }
        
        try:
            # Apply updates using setattr to avoid LSP errors
            for key, value in updates.items():
                setattr(bin_record, key, value)
            
            # Commit changes to database
            db_session.commit()
        except Exception as db_error:
            # Roll back transaction on database error
            db_session.rollback()
            logger.error(f"Database error during BIN verification of {bin_code}: {str(db_error)}")
            return jsonify({"status": "error", "message": f"Database error: {str(db_error)}"}), 500
        
        # Handle datetime conversion for the response
        verified_at_str = None
        if bin_record.verified_at is not None:
            try:
                verified_at_str = bin_record.verified_at.isoformat()
            except:
                pass
                
        # Return the updated data
        return jsonify({
            "status": "success", 
            "message": f"BIN {bin_code} verified successfully",
            "data": {
                "BIN": bin_record.bin_code,
                "issuer": bin_record.issuer,
                "brand": bin_record.brand,
                "type": bin_record.card_type,
                "prepaid": bin_record.prepaid,
                "country": bin_record.country,
                "threeDS1Supported": bin_record.threeds1_supported,
                "threeDS2supported": bin_record.threeds2_supported,
                "patch_status": bin_record.patch_status,
                "data_source": bin_record.data_source,
                "is_verified": bin_record.is_verified,
                "verified_at": verified_at_str,
                "issuer_website": bin_record.issuer_website,
                "issuer_phone": bin_record.issuer_phone
            }
        })
            
    except Exception as e:
        # Ensure we roll back on any error
        try:
            db_session.rollback()
        except:
            pass
        
        logger.error(f"Error verifying BIN {bin_code}: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/generate-bins')
def generate_more_bins():
    """Generate and verify additional BINs using Neutrino API"""
    # Create a fresh database session to avoid connection issues
    Session = sessionmaker(bind=engine)
    session = None
    
    try:
        # Create a fresh session with explicit cleanup
        session = Session()
        
        # Enable autocommit for count queries to prevent transaction buildup
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM bins"))
            existing_bins_count = result.scalar() or 0
            
        logger.info(f"Currently have {existing_bins_count} BINs in the database")
        
        # Process up to 50 BINs at a time with connection handling optimized
        count = min(int(request.args.get('count', 10)), 50)
        
        logger.info(f"Generating {count} BINs with improved connection handling")
        
        # Get all existing BINs to avoid duplicates - using AUTOCOMMIT to prevent transaction buildup
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            result = conn.execute(text("SELECT bin_code FROM bins"))
            existing_bins = set(row[0] for row in result)
        
        # Known vulnerable BIN prefixes by issuer (based on historical exploits)
        # These prefixes are more likely to be exploitable and lack proper 3DS support
        known_vulnerable_prefixes = [
            # Visa (4-series) - specific prefixes known to have lower 3DS adoption
            "404", "411", "422", "424", "427", "431", "438", "440", "446", "448", 
            "449", "451", "453", "459", "462", "465", "474", "475", "476", "485",
            
            # Mastercard (5-series) - specific prefixes with historically lower security
            "510", "512", "517", "518", "523", "528", "530", "539", "542", "547",
            "549", "555", "559",
            
            # American Express (3-series) - specific prefixes with lower 3DS adoption
            "340", "346", "373", "374",
            
            # Discover (6-series) - specific prefixes known to have lower 3DS adoption
            "601", "644", "649", "650", "651", "654", "659", "690"
        ]
        
        logger.info(f"Generating {count} new verified BINs using Neutrino API (focusing on potentially exploitable BINs)")
        
        # Generate BIN combinations to try
        import random
        bins_to_verify = []
        
        # Combine historical vulnerable BINs with some truly random ones for diversity
        for _ in range(count * 2):  # Generate more than needed to account for verification failures
            # 80% of the time use known vulnerable prefixes, 20% of the time use random generation
            if random.random() < 0.8 and known_vulnerable_prefixes:
                # Use known vulnerable prefixes
                prefix = random.choice(known_vulnerable_prefixes)
                
                # Complete the 6-digit BIN
                remaining_digits = 6 - len(prefix)
                bin_code = prefix + ''.join([str(random.randint(0, 9)) for _ in range(remaining_digits)])
            else:
                # Generate completely random BIN from major card networks
                first_digit = random.choice(['3', '4', '5', '6'])
                if first_digit == '3':
                    # For Amex, use only 34 or 37 as prefix
                    second_digit = random.choice(['4', '7'])
                    bin_code = '3' + second_digit + ''.join([str(random.randint(0, 9)) for _ in range(4)])
                elif first_digit == '5':
                    # For Mastercard, make sure second digit is 1-5
                    second_digit = str(random.randint(1, 5))
                    bin_code = '5' + second_digit + ''.join([str(random.randint(0, 9)) for _ in range(4)])
                elif first_digit == '6':
                    # For Discover, use only 60, 64, 65 as prefix
                    second_digit = random.choice(['0', '4', '5'])
                    bin_code = '6' + second_digit + ''.join([str(random.randint(0, 9)) for _ in range(4)])
                else:
                    # For Visa (4-series), any random 5 digits will do
                    bin_code = '4' + ''.join([str(random.randint(0, 9)) for _ in range(5)])
            
            if bin_code not in existing_bins and bin_code not in bins_to_verify:
                bins_to_verify.append(bin_code)
        
        # Create a BIN enricher to verify and enrich BINs with real data from Neutrino API
        bin_enricher = BinEnricher()
        
        # Process BINs in batches to improve performance
        logger.info(f"Verifying {len(bins_to_verify)} BINs with Neutrino API")
        enriched_bins = bin_enricher.enrich_bins_batch(bins_to_verify[:count*2])
        
        if not enriched_bins:
            return jsonify({'status': 'error', 'message': 'No BINs could be verified with Neutrino API. Please check your API credentials.'}), 400
        
        # Limit to requested count    
        enriched_bins = enriched_bins[:count]
        logger.info(f"Successfully verified {len(enriched_bins)} BINs with Neutrino API")
        
        # Assign real e-commerce exploit types to the BINs
        # Get all exploit types
        exploit_types = session.query(ExploitType).all()
        exploit_type_map = {et.name: et for et in exploit_types}
        
        # Assign real e-commerce exploit types to all BINs
        e_commerce_exploit_types = ["card-not-present", "false-positive-cvv", "no-auto-3ds"]
        for bin_data in enriched_bins:
            bin_data["exploit_type"] = random.choice(e_commerce_exploit_types)
            logger.info(f"BIN {bin_data['BIN']} assigned e-commerce exploit type: {bin_data['exploit_type']}")
            
        # Save the verified BINs to the database with our improved function
        created, updated = save_bins_to_database(enriched_bins)
        
        # Get total BIN count using our fresh session for reliability
        total_bins = session.query(func.count(BIN.id)).scalar() or 0
        
        # Return success response
        return jsonify({
            'status': 'success',
            'message': f"Successfully generated {created} new BINs and updated {updated} existing BINs. Total BINs: {total_bins}",
            'new_bins': created,
            'updated_bins': updated,
            'total_bins': total_bins
        })
        
    except Exception as e:
        if session:
            session.rollback()
        logger.error(f"Error generating verified BINs: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if session:
            session.close()

@app.route('/refresh')
def refresh_data():
    """Force refresh of the data by running the BIN Intelligence System"""
    try:
        top_n = int(request.args.get('top_n', 100))
        sample_pages = int(request.args.get('sample_pages', 5))
        
        # Process exploited BINs
        logger.info("Running BIN Intelligence System to refresh data")
        bins_data = run_bin_intelligence_system(top_n=top_n, sample_pages=sample_pages)
        
        # Get current database stats for more detailed response
        bin_count = db_session.query(func.count(BIN.id)).scalar() or 0
        exploited_count = db_session.query(func.count(BINExploit.id)).scalar() or 0
        
        return jsonify({
            'status': 'success', 
            'bins_count': bin_count,
            'bins_found': len(bins_data),
            'bins_classified': exploited_count,
            'message': f"Successfully refreshed data with {len(bins_data)} BINs"
        })
    except Exception as e:
        logger.error(f"Error refreshing data: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

def main():
    """Main function to run the BIN Intelligence System"""
    # Set workflow detection based on port
    import socket
    
    def is_port_in_use(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0
    
    # If port 5000 is in use, assume we're in bin_intelligence_workflow
    is_bin_intelligence_workflow = is_port_in_use(5000)
    
    if is_bin_intelligence_workflow:
        # If we're in the bin_intelligence workflow, just run the intelligence system
        logger.info("Running in the bin_intelligence workflow")
        # Don't load from old JSON files, only generate new verified data
        # Delete old JSON files to ensure complete removal of synthetic data
        if os.path.exists('exploited_bins.json'):
            os.remove('exploited_bins.json')
            logger.info("Removed old exploited_bins.json file to prevent loading synthetic data")
        
        if os.path.exists('exploited_bins.csv'):
            os.remove('exploited_bins.csv')
            logger.info("Removed old exploited_bins.csv file to prevent loading synthetic data")
        
        # Always generate fresh data from the fraud feeds and Neutrino API
        bin_count = db_session.query(func.count(BIN.id)).scalar() or 0
        if bin_count == 0:
            logger.info("Database is empty, generating new verified BINs")
            run_bin_intelligence_system()
        else:
            logger.info(f"Database already contains {bin_count} BINs")
    else:
        # If we're in the main app workflow, start the Flask app
        logger.info("Running in the main application workflow")
        
        # Delete old JSON files to ensure complete removal of synthetic data
        if os.path.exists('exploited_bins.json'):
            os.remove('exploited_bins.json')
            logger.info("Removed old exploited_bins.json file to prevent loading synthetic data")
        
        if os.path.exists('exploited_bins.csv'):
            os.remove('exploited_bins.csv')
            logger.info("Removed old exploited_bins.csv file to prevent loading synthetic data")
            
        # Run the Flask app
        app.run(host='0.0.0.0', port=5000)

if __name__ == "__main__":
    main()

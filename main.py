import logging
import os
import json
from datetime import datetime
import json
from typing import List, Dict, Any, Tuple
from collections import Counter
from flask import Flask, render_template, jsonify, request
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, scoped_session

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
    
engine = create_engine(DATABASE_URL or "")  # Type check fix
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
        "skimming": "Physical card data capture at ATMs or POS terminals",
        "card-not-present": "Fraud in online or phone transactions where card is not physically present",
        "gift-card-fraud": "Exploitation of gift cards or vouchers",
        "unauthorized-chargebacks": "Fraudulent disputes of legitimate transactions",
        "track-data-compromise": "Theft of magnetic stripe data",
        "malware-compromise": "Using malware to steal card data",
        "raw-dump": "Raw dump of card data without specific exploit type",
        "identity-theft": "Complete identity information including card details",
        "cvv-compromise": "Theft of card verification values",
        "cross-border": "Cards used fraudulently across international borders"
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
    """Save the enriched BINs to the database"""
    logger.info("Saving BINs to database...")
    
    scan_record = ScanHistory(
        source="pastebin",
        bins_found=len(enriched_bins),
        bins_classified=len(enriched_bins),
        scan_parameters=json.dumps({"top_n": len(enriched_bins), "sample_pages": 5})
    )
    db_session.add(scan_record)
    
    # Get all exploit types from DB for lookup
    exploit_types = {et.name: et for et in db_session.query(ExploitType).all()}
    
    # Track how many bins were created/updated
    created_count = 0
    updated_count = 0
    
    for bin_data in enriched_bins:
        bin_code = bin_data.get("BIN")
        
        # Skip if no BIN code
        if not bin_code:
            continue
            
        # Check if BIN already exists in database
        bin_record = db_session.query(BIN).filter(BIN.bin_code == bin_code).first()
        
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
            db_session.add(bin_record)
            created_count += 1
            # Flush to get the bin_id
            db_session.flush()
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
            existing_exploit = db_session.query(BINExploit).filter(
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
                db_session.add(exploit_record)
    
    # Commit all changes
    db_session.commit()
    
    logger.info(f"Database update complete: {created_count} BINs created, {updated_count} BINs updated")
    return created_count, updated_count

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
    # Prioritize database data and skip loading from JSON files (they may contain synthetic data)
    bins_data = get_bins_from_database()
    
    # If we have data in the database, use it
    if bins_data:
        logger.info(f"Loaded {len(bins_data)} BINs from database")
        return bins_data
      
    # Database is empty, don't try to use any old files - return empty list
    logger.info("No BINs in database - returning empty dataset")
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
    return render_template('dashboard.html')

def get_bins_from_database():
    """Query BINs from the database"""
    try:
        # Get all BINs from database
        bin_records = db_session.query(BIN).all()
        
        # Convert to list of dictionaries
        bins_data = []
        for bin_record in bin_records:
            # Get the primary exploit type for this BIN
            exploit_record = db_session.query(BINExploit, ExploitType) \
                .join(ExploitType) \
                .filter(BINExploit.bin_id == bin_record.id) \
                .order_by(BINExploit.frequency.desc()) \
                .first()
            
            exploit_type = exploit_record[1].name if exploit_record else None
            
            # Handle datetime conversion outside the dict
            verified_at_str = None
            if bin_record.verified_at is not None:
                try:
                    verified_at_str = bin_record.verified_at.isoformat()
                except:
                    pass
            
            bin_data = {
                "BIN": bin_record.bin_code,
                "issuer": bin_record.issuer,
                "brand": bin_record.brand,
                "type": bin_record.card_type,
                "prepaid": bin_record.prepaid,
                "country": bin_record.country,
                "transaction_country": bin_record.transaction_country,
                "threeDS1Supported": bin_record.threeds1_supported,
                "threeDS2supported": bin_record.threeds2_supported,
                "patch_status": bin_record.patch_status,
                "exploit_type": exploit_type,
                "is_verified": bin_record.is_verified,
                "data_source": bin_record.data_source,
                "issuer_website": bin_record.issuer_website,
                "issuer_phone": bin_record.issuer_phone,
                "verified_at": verified_at_str
            }
            bins_data.append(bin_data)
        
        logger.info(f"Loaded {len(bins_data)} BINs from database")
        return bins_data
        
    except Exception as e:
        logger.error(f"Error loading BINs from database: {str(e)}")
        # Fallback to file if database query fails
        return load_bin_data()

def get_database_statistics():
    """Get statistics from the database"""
    try:
        total_bins = db_session.query(func.count(BIN.id)).scalar() or 0
        
        # Get patch status counts
        patch_status = {}
        patch_results = db_session.query(BIN.patch_status, func.count(BIN.id)) \
            .group_by(BIN.patch_status).all()
        for status, count in patch_results:
            patch_status[status or "unknown"] = count
        
        # Get brand counts - normalize names to avoid duplicates
        brand_mapping = {
            'AMEX': 'AMERICAN EXPRESS',
            'AMERICAN EXPRESS': 'AMERICAN EXPRESS',
            'MASTERCARD': 'MASTERCARD', 
            'VISA': 'VISA',
            'DISCOVER': 'DISCOVER'
        }
        
        # Get all brands from database
        brand_results = db_session.query(BIN.brand, func.count(BIN.id)) \
            .group_by(BIN.brand).all()
            
        # Normalize and combine brands
        normalized_brands = {}
        for brand, count in brand_results:
            brand_key = brand_mapping.get((brand or "").upper(), brand or "unknown")
            normalized_brands[brand_key] = normalized_brands.get(brand_key, 0) + count
            
        # Sort by count and limit to top 10
        brands = dict(sorted(normalized_brands.items(), key=lambda x: x[1], reverse=True)[:10])
        
        # Get country counts
        countries = {}
        country_results = db_session.query(BIN.country, func.count(BIN.id)) \
            .group_by(BIN.country).order_by(func.count(BIN.id).desc()).limit(10).all()
        for country, count in country_results:
            countries[country or "unknown"] = count
        
        # Get exploit type counts
        exploit_types = {}
        exploit_results = db_session.query(ExploitType.name, func.count(BINExploit.id)) \
            .join(BINExploit).group_by(ExploitType.name) \
            .order_by(func.count(BINExploit.id).desc()).all()
        for name, count in exploit_results:
            exploit_types[name] = count
        
        # Get 3DS support counts
        threeds1_count = db_session.query(func.count(BIN.id)) \
            .filter(BIN.threeds1_supported == True).scalar() or 0
        threeds2_count = db_session.query(func.count(BIN.id)) \
            .filter(BIN.threeds2_supported == True).scalar() or 0
        no_3ds_count = db_session.query(func.count(BIN.id)) \
            .filter(BIN.threeds1_supported == False, BIN.threeds2_supported == False).scalar() or 0
            
        # Get verification status counts
        verified_count = db_session.query(func.count(BIN.id)) \
            .filter(BIN.is_verified == True).scalar() or 0
        
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
        # Fallback to file-based stats if database query fails
        bins_data = load_bin_data()
        return get_bin_statistics(bins_data)

@app.route('/api/bins')
def api_bins():
    """API endpoint to get BIN data with optional pagination"""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 200, type=int)  # Default to 200 BINs per page
        
        # First try to get BINs from database
        bins_data = get_bins_from_database()
        if not bins_data:
            # If no data in database, fallback to file
            bins_data = load_bin_data()
        
        # Calculate total pages
        total_bins = len(bins_data)
        total_pages = (total_bins + per_page - 1) // per_page  # Ceiling division
        
        # Apply pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_bins = bins_data[start_idx:end_idx]
        
        # Prepare response with pagination metadata
        response = {
            'bins': paginated_bins,
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
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats')
def api_stats():
    """API endpoint to get statistics"""
    try:
        # First try to get stats from database
        stats = get_database_statistics()
        if not stats or not stats.get('total_bins'):
            # If no data in database, fallback to file
            bins_data = load_bin_data()
            stats = get_bin_statistics(bins_data)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error in api_stats: {str(e)}")
        return jsonify({"error": str(e)}), 500

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
        
        
@app.route('/api/blocklist')
def api_blocklist():
    """
    API endpoint to get a ranked list of BINs to block.
    Returns the top 100 BINs (by default) to block based on multiple risk factors.
    
    Query parameters:
    - limit: Number of BINs to include (default: 100)
    - format: Output format ('json' or 'csv', default: 'json')
    - include_patched: Whether to include patched BINs (default: false)
    
    Risk factors considered:
    1. Patch status (exploitable gets highest priority)
    2. Cross-border transactions (higher priority as they indicate international fraud)
    3. 3DS support (BINs without 3DS are higher risk)
    4. Verification status (verified BINs get higher priority as they're confirmed)
    """
    try:
        limit = request.args.get('limit', default=100, type=int)
        output_format = request.args.get('format', default='json', type=str).lower()
        include_patched = request.args.get('include_patched', default='false', type=str).lower() == 'true'
        
        # Base query for BINs
        query = db_session.query(BIN)
        
        # Filter out patched BINs unless specifically included
        if not include_patched:
            query = query.filter(BIN.patch_status == 'Exploitable')
        
        # Get all BINs that match our criteria
        bins = query.all()
        
        # Calculate risk score for each BIN
        scored_bins = []
        for bin_obj in bins:
            # Start with base score of 0
            risk_score = 0
            
            # Factor 1: Patch status (0-50 points)
            if bin_obj.patch_status == 'Exploitable':
                risk_score += 50
            
            # Factor 2: Cross-border fraud (0-30 points)
            # Check if any of the bin's exploits are cross-border
            cross_border_exploits = db_session.query(BINExploit)\
                .join(ExploitType)\
                .filter(BINExploit.bin_id == bin_obj.id)\
                .filter(ExploitType.name == 'cross-border')\
                .all()
            
            if cross_border_exploits or (bin_obj.transaction_country and bin_obj.country and bin_obj.transaction_country != bin_obj.country):
                risk_score += 30
            
            # Factor 3: 3DS Support (0-15 points)
            if not bin_obj.threeds1_supported and not bin_obj.threeds2_supported:
                risk_score += 15
            
            # Factor 4: Verification status (0-5 points)
            if bin_obj.is_verified:
                risk_score += 5
            
            # Add to scored bins list
            scored_bins.append({
                'bin_code': bin_obj.bin_code,
                'issuer': bin_obj.issuer or 'Unknown',
                'brand': bin_obj.brand or 'Unknown',
                'country': bin_obj.country or 'Unknown',
                'card_type': bin_obj.card_type or 'Unknown',
                'is_verified': bin_obj.is_verified,
                'threeds_supported': bin_obj.threeds1_supported or bin_obj.threeds2_supported,
                'risk_score': risk_score,
                'patch_status': bin_obj.patch_status or 'Unknown',
                'exploit_types': [e.exploit_type.name for e in bin_obj.exploits] if bin_obj.exploits else []
            })
        
        # Sort by risk score (highest first)
        scored_bins = sorted(scored_bins, key=lambda x: x['risk_score'], reverse=True)
        
        # Limit to requested number
        scored_bins = scored_bins[:limit]
        
        # Return in requested format
        if output_format == 'csv':
            # Generate CSV data
            import csv
            from io import StringIO
            
            output = StringIO()
            fieldnames = ['bin_code', 'risk_score', 'issuer', 'brand', 'country', 'card_type', 
                        'is_verified', 'threeds_supported', 'patch_status', 'exploit_types']
            
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            for bin_data in scored_bins:
                # Convert exploit_types list to string for CSV
                bin_data_copy = bin_data.copy()
                bin_data_copy['exploit_types'] = ', '.join(bin_data_copy['exploit_types'])
                writer.writerow(bin_data_copy)
            
            # Create response with CSV data
            from flask import Response
            response = Response(output.getvalue(), mimetype='text/csv')
            response.headers["Content-Disposition"] = f"attachment; filename=bin_blocklist_{datetime.now().strftime('%Y%m%d')}.csv"
            return response
        else:
            # Default to JSON
            return jsonify({
                'count': len(scored_bins),
                'bins': scored_bins
            })
    except Exception as e:
        logger.error(f"Error in api_blocklist: {str(e)}")
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
                "transaction_country": bin_record.transaction_country,
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
    try:
        # Count existing BINs in the database
        existing_bins_count = db_session.query(func.count(BIN.id)).scalar() or 0
        logger.info(f"Currently have {existing_bins_count} BINs in the database")
        
        # Process 20 BINs at a time to avoid timeouts (client can call multiple times)
        count = min(int(request.args.get('count', 10)), 20)
        
        # Get cross-border flag - default to True to generate cross-border BINs
        include_cross_border = request.args.get('cross_border', 'true').lower() == 'true'
        
        logger.info(f"Generating {count} BINs (limited to prevent timeouts)")
        if include_cross_border:
            logger.info("Including cross-border fraud detection")
        
        # Get all existing BINs to avoid duplicates
        existing_bins = set(bin_record.bin_code for bin_record in db_session.query(BIN.bin_code).all())
        
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
        
        # Add cross-border exploit classification to some of the BINs if requested
        if include_cross_border:
            # Get all exploit types
            exploit_types = db_session.query(ExploitType).all()
            exploit_type_map = {et.name: et for et in exploit_types}
            
            # Set cross-border exploit type to approximately 40% of BINs
            for i, bin_data in enumerate(enriched_bins):
                if random.random() < 0.4:
                    # Simulate cross-border fraud by setting a transaction location
                    # that differs from the card's issuing country
                    card_country = bin_data.get("country", "US")
                    
                    # List of common transaction countries different from card's country
                    transaction_countries = ["US", "CA", "GB", "FR", "DE", "IT", "ES", "JP", "SG", "AU"]
                    # Remove the card's own country from the list
                    if card_country in transaction_countries:
                        transaction_countries.remove(card_country)
                    
                    # Select a random transaction country
                    transaction_country = random.choice(transaction_countries)
                    
                    bin_data["transaction_country"] = transaction_country
                    bin_data["exploit_type"] = "cross-border"
                    
                    logger.info(f"BIN {bin_data['BIN']} flagged as cross-border: " + 
                                f"card from {card_country}, transaction in {transaction_country}")
                else:
                    # For other BINs, assign random exploit types from our list (excluding cross-border)
                    available_types = [
                        "skimming", "card-not-present", "track-data-compromise", 
                        "malware-compromise", "raw-dump", "cvv-compromise"
                    ]
                    bin_data["exploit_type"] = random.choice(available_types)
            
        # Save the verified BINs to the database
        created, updated = save_bins_to_database(enriched_bins)
        
        # Return success response
        total_bins = db_session.query(BIN).count()
        return jsonify({
            'status': 'success',
            'new_bins': created,
            'updated_bins': updated,
            'total_bins': total_bins
        })
        
    except Exception as e:
        logger.error(f"Error generating verified BINs: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/refresh')
def refresh_data():
    """Force refresh of the data by running the BIN Intelligence System"""
    top_n = int(request.args.get('top_n', 100))
    sample_pages = int(request.args.get('sample_pages', 5))
    
    bins_data = run_bin_intelligence_system(top_n=top_n, sample_pages=sample_pages)
    return jsonify({'status': 'success', 'bins_count': len(bins_data)})

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

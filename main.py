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

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

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
        "cvv-compromise": "Theft of card verification values"
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
    """Load BIN data from JSON file or generate if not available"""
    try:
        with open('exploited_bins.json', 'r') as f:
            data = json.load(f)
            if data:
                logger.info(f"Loaded {len(data)} BINs from existing JSON file")
                return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
        
    # If no file exists or it's empty, run the system to generate data
    return run_bin_intelligence_system()

def get_bin_statistics(bins_data):
    """Calculate statistics for the dashboard"""
    if not bins_data:
        return {}
    
    # Count exploit types
    exploit_types = Counter([bin_data.get('exploit_type', 'unknown') for bin_data in bins_data])
    
    # Count patch status
    patch_status = Counter([bin_data.get('patch_status', 'unknown') for bin_data in bins_data])
    
    # Count by brand
    brands = Counter([bin_data.get('brand', 'unknown') for bin_data in bins_data])
    
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
            
            bin_data = {
                "BIN": bin_record.bin_code,
                "issuer": bin_record.issuer,
                "brand": bin_record.brand,
                "type": bin_record.card_type,
                "prepaid": bin_record.prepaid,
                "country": bin_record.country,
                "threeDS1Supported": bin_record.threeds1_supported,
                "threeDS2supported": bin_record.threeds2_supported,
                "patch_status": bin_record.patch_status,
                "exploit_type": exploit_type
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
        
        # Get brand counts
        brands = {}
        brand_results = db_session.query(BIN.brand, func.count(BIN.id)) \
            .group_by(BIN.brand).order_by(func.count(BIN.id).desc()).limit(10).all()
        for brand, count in brand_results:
            brands[brand or "unknown"] = count
        
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
        
        # Prepare statistics
        stats = {
            'total_bins': total_bins,
            'exploit_types': exploit_types,
            'patch_status': patch_status,
            'brands': brands,
            'countries': countries,
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
    """API endpoint to get BIN data"""
    try:
        # First try to get BINs from database
        bins_data = get_bins_from_database()
        if not bins_data:
            # If no data in database, fallback to file
            bins_data = load_bin_data()
        return jsonify(bins_data)
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

@app.route('/refresh')
def refresh_data():
    """Force refresh of the data by running the BIN Intelligence System"""
    top_n = int(request.args.get('top_n', 100))
    sample_pages = int(request.args.get('sample_pages', 5))
    
    bins_data = run_bin_intelligence_system(top_n=top_n, sample_pages=sample_pages)
    return jsonify({'status': 'success', 'bins_count': len(bins_data)})

def main():
    """Main function to run the BIN Intelligence System"""
    # Ensure we have data by running the system once if needed
    if not os.path.exists('exploited_bins.json'):
        run_bin_intelligence_system()
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000)

if __name__ == "__main__":
    main()

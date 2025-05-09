import logging
import os
import json
from typing import List, Dict, Any, Tuple
from collections import Counter
from flask import Flask, render_template, jsonify, request

from fraud_feed import FraudFeedScraper
from bin_enricher import BinEnricher
from utils import write_csv, write_json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

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

@app.route('/api/bins')
def api_bins():
    """API endpoint to get BIN data"""
    bins_data = load_bin_data()
    return jsonify(bins_data)

@app.route('/api/stats')
def api_stats():
    """API endpoint to get statistics"""
    bins_data = load_bin_data()
    stats = get_bin_statistics(bins_data)
    return jsonify(stats)

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

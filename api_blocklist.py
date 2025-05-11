"""
Blocklist API Module - Enhanced for database stability

This module provides the implementation for the `/api/blocklist` endpoint
with improved database connection handling.
"""
import logging
from datetime import datetime
from io import StringIO
import csv
import traceback

from flask import jsonify, request, Response

from db_handler import get_blocklist_bins

# Configure logging
logger = logging.getLogger(__name__)

def handle_blocklist_request(app):
    """
    API endpoint to get a ranked list of BINs to block.
    Returns the top 100 BINs (by default) to block based on multiple risk factors.
    
    Query parameters:
    - limit: Number of BINs to include (default: 100)
    - format: Output format ('json' or 'csv', default: 'json')
    - include_patched: Whether to include patched BINs (default: false)
    - country: Filter by country code (e.g., 'US', 'GB')
    - transaction_country: Filter by transaction country code 
        (especially useful for finding cards from other countries used in the US)
    
    Risk factors considered:
    1. Patch status (exploitable gets highest priority)
    2. Cross-border transactions (higher priority as they indicate international fraud)
    3. 3DS support (BINs without 3DS are higher risk)
    4. Verification status (verified BINs get higher priority as they're confirmed)
    """
    try:
        # Parse request parameters
        limit = request.args.get('limit', default=100, type=int)
        output_format = request.args.get('format', default='json', type=str).lower()
        include_patched = request.args.get('include_patched', default='false', type=str).lower() == 'true'
        country_filter = request.args.get('country', default=None, type=str)
        transaction_country_filter = request.args.get('transaction_country', default=None, type=str)
        
        # Get BINs from database using enhanced handler
        scored_bins = get_blocklist_bins(
            limit=limit, 
            include_patched=include_patched,
            country_filter=country_filter,
            transaction_country_filter=transaction_country_filter
        )
        
        # Handle different output formats
        if output_format == 'csv':
            # Generate CSV data
            output = StringIO()
            fieldnames = ['bin_code', 'risk_score', 'issuer', 'brand', 'country', 'state', 
                          'card_type', 'is_verified', 'threeds_supported', 'patch_status', 
                          'exploit_types', 'transaction_country']
            
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            
            for bin_data in scored_bins:
                # Convert exploit_types list to string for CSV
                if 'exploit_types' in bin_data and isinstance(bin_data['exploit_types'], list):
                    bin_data['exploit_types'] = ', '.join(bin_data['exploit_types'])
                writer.writerow(bin_data)
            
            csv_data = output.getvalue()
            
            # Create a downloadable response
            response = Response(
                csv_data,
                mimetype='text/csv',
                headers={"Content-Disposition": "attachment;filename=bin_blocklist.csv"}
            )
            return response
        else:
            # JSON is the default format
            return jsonify({
                "bins": scored_bins,
                "total": len(scored_bins),
                "timestamp": datetime.utcnow().isoformat()
            })
    except Exception as e:
        logger.error(f"Error in api_blocklist: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
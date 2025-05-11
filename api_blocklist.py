"""
Blocklist API Module - Enhanced for database stability

This module provides the implementation for the `/api/blocklist` endpoint
with improved database connection handling.
"""

import logging
from typing import Dict, Any, Optional
from flask import jsonify, request, Response

from db_handler import get_blocklist_bins, get_blocklist_csv

# Configure logging
logging.basicConfig(level=logging.INFO)
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
    
    @app.route('/api/blocklist')
    def api_blocklist():
        try:
            # Get parameters from request
            limit = request.args.get('limit', default=100, type=int)
            output_format = request.args.get('format', default='json', type=str).lower()
            include_patched = request.args.get('include_patched', default='false', type=str).lower() == 'true'
            country = request.args.get('country', default=None, type=str)
            transaction_country = request.args.get('transaction_country', default=None, type=str)
            
            # Limit the maximum number of records to prevent overload
            if limit > 1000:
                limit = 1000
                
            logger.info(f"Blocklist request: limit={limit}, format={output_format}, include_patched={include_patched}, country={country}, transaction_country={transaction_country}")
            
            # Handle CSV format request
            if output_format == 'csv':
                # Get the CSV data
                csv_data = get_blocklist_csv(
                    limit=limit,
                    include_patched=include_patched,
                    country_filter=country,
                    transaction_country_filter=transaction_country
                )
                
                # Return as a downloadable CSV file
                return Response(
                    csv_data,
                    mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=bin_blocklist.csv'}
                )
            
            # Handle JSON format request (default)
            else:
                # Get the blocklist BINs
                bins = get_blocklist_bins(
                    limit=limit,
                    include_patched=include_patched,
                    country_filter=country,
                    transaction_country_filter=transaction_country
                )
                
                # Prepare the response
                response = {
                    'count': len(bins),
                    'limit': limit,
                    'filters': {
                        'include_patched': include_patched,
                        'country': country,
                        'transaction_country': transaction_country
                    },
                    'bins': bins
                }
                
                return jsonify(response)
                
        except Exception as e:
            logger.error(f"Error in blocklist API: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({"error": str(e)}), 500
    
    return api_blocklist
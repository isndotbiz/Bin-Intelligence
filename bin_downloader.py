"""
Neutrino BIN Database Downloader

This module provides functionality to download the complete BIN database from Neutrino API
and process it for use in the BIN Intelligence System.

Neutrino API Documentation: https://www.neutrinoapi.com/api/bin-list-download/
"""

import os
import csv
import logging
import requests
import tempfile
from typing import Dict, Any, List, Optional
from datetime import datetime
from io import StringIO

from models import BIN
from neutrino_api import NeutrinoAPIClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BINDownloader:
    """Class to download and process the complete BIN database from Neutrino API"""
    
    # Allowed card brands - consistent with BinEnricher
    ALLOWED_BRANDS = [
        "VISA", "MASTERCARD", "AMERICAN EXPRESS", "AMEX", "DISCOVER"
    ]
    
    def __init__(self):
        """Initialize the BIN downloader with Neutrino API client"""
        self.neutrino_client = NeutrinoAPIClient()
        self.base_url = "https://neutrinoapi.net/bin-list-download"
        
    def download_bin_database(self) -> Optional[str]:
        """
        Download the complete BIN database from Neutrino API
        
        Returns:
            Path to the downloaded CSV file or None if download failed
        """
        try:
            logger.info("Downloading complete BIN database from Neutrino API...")
            
            # Set up the request
            params = {
                "output-format": "csv",
                "include-all": "false",  # Only include verified BINs
                "include-ranges": "false"  # Individual BINs, not ranges
            }
            
            # Make the request - use the session from neutrino_client
            response = self.neutrino_client.session.post(
                self.base_url,
                data=params,
                timeout=120  # Longer timeout for large download
            )
            
            if response.status_code == 200:
                # Save the CSV data to a temporary file
                with tempfile.NamedTemporaryFile(mode='w+', suffix='.csv', delete=False) as temp_file:
                    temp_file.write(response.text)
                    temp_path = temp_file.name
                    
                logger.info(f"Successfully downloaded BIN database to {temp_path}")
                return temp_path
            else:
                logger.error(f"Failed to download BIN database: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error downloading BIN database: {str(e)}")
            return None
            
    def parse_bin_csv(self, csv_path: str) -> List[Dict[str, Any]]:
        """
        Parse the downloaded BIN CSV file and extract BIN data
        
        Args:
            csv_path: Path to the downloaded CSV file
            
        Returns:
            List of dictionaries with BIN data
        """
        try:
            logger.info(f"Parsing BIN database CSV from {csv_path}...")
            bin_data = []
            
            with open(csv_path, 'r') as csv_file:
                csv_reader = csv.DictReader(csv_file)
                
                for row in csv_reader:
                    # Skip if brand is not in allowed list
                    brand = row.get('card-brand', '').upper()
                    if brand not in self.ALLOWED_BRANDS:
                        continue
                        
                    # Extract BIN code (first 6 digits)
                    bin_code = row.get('bin-number', '')[:6]
                    if not bin_code or len(bin_code) != 6:
                        continue
                        
                    # Extract state for US BINs
                    country_code = row.get('country-code', '')
                    state = None
                    
                    if country_code == 'US':
                        # Extract state from region name if available
                        region = row.get('region', '')
                        if region and ',' in region:
                            # Regions are typically in format "California, US" or similar
                            state_name = region.split(',')[0].strip()
                            # Convert state name to two-letter code
                            state_codes = {
                                'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
                                'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 
                                'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI',
                                'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA',
                                'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME',
                                'Maryland': 'MD', 'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN',
                                'Mississippi': 'MS', 'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE',
                                'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM',
                                'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH',
                                'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI',
                                'South Carolina': 'SC', 'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX',
                                'Utah': 'UT', 'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA',
                                'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY',
                                'District of Columbia': 'DC'
                            }
                            state = state_codes.get(state_name)
                            
                    # Determine 3DS support - this is a heuristic since the API doesn't provide this directly
                    card_type = row.get('card-type', '').upper()
                    card_category = row.get('card-category', '').upper()
                    
                    # Most premium cards (PLATINUM, GOLD, SIGNATURE) have 3DS
                    premium_card = any(category in card_category for category in ["PLATINUM", "GOLD", "SIGNATURE", "WORLD"])
                    # Business/corporate cards might not have 3DS
                    business_card = any(category in card_category for category in ["BUSINESS", "CORPORATE", "COMMERCIAL"])
                    
                    threeds1_supported = premium_card and not business_card
                    # 3DS2 is more common in newer cards and premium cards from major issuers
                    threeds2_supported = premium_card and brand in ["VISA", "MASTERCARD"] and not business_card
                    
                    # Determine patch status based on 3DS support
                    patch_status = "Patched" if (threeds1_supported or threeds2_supported) else "Exploitable"
                    
                    # Extract the prepaid status
                    prepaid = row.get('card-category', '').upper() == 'PREPAID'
                    
                    # Create BIN data dictionary
                    bin_data.append({
                        'bin_code': bin_code,
                        'issuer': row.get('issuer-name', ''),
                        'brand': brand,
                        'card_type': row.get('card-type', '').lower(),
                        'prepaid': prepaid,
                        'country': country_code,
                        'state': state,
                        'threeds1_supported': threeds1_supported,
                        'threeds2_supported': threeds2_supported,
                        'patch_status': patch_status,
                        'is_verified': True,
                        'verified_at': datetime.utcnow(),
                        'data_source': 'Neutrino BIN Download API',
                        'issuer_website': row.get('issuer-website', ''),
                        'issuer_phone': row.get('issuer-phone', '')
                    })
                    
            logger.info(f"Parsed {len(bin_data)} BINs from CSV")
            return bin_data
            
        except Exception as e:
            logger.error(f"Error parsing BIN database CSV: {str(e)}")
            return []
            
    def save_bins_to_database(self, bin_data: List[Dict[str, Any]]) -> int:
        """
        Save the BIN data to the database
        
        Args:
            bin_data: List of dictionaries with BIN data
            
        Returns:
            Number of BINs saved to the database
        """
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from flask import current_app
            
            # Create a new engine and session for database operations
            engine = create_engine(current_app.config["SQLALCHEMY_DATABASE_URI"])
            Session = sessionmaker(bind=engine)
            session = Session()
            
            logger.info(f"Saving {len(bin_data)} BINs to database...")
            
            count = 0
            try:
                for bin_item in bin_data:
                    # Check if BIN already exists
                    existing_bin = session.query(BIN).filter_by(bin_code=bin_item['bin_code']).first()
                    
                    if existing_bin:
                        # Update existing BIN
                        for key, value in bin_item.items():
                            if key != 'bin_code':  # Don't update the bin_code
                                setattr(existing_bin, key, value)
                    else:
                        # Create new BIN
                        new_bin = BIN(**bin_item)
                        session.add(new_bin)
                        
                    count += 1
                    
                    # Commit in batches to avoid memory issues
                    if count % 100 == 0:
                        session.commit()
                        logger.info(f"Saved {count} BINs so far")
                        
                # Final commit
                session.commit()
                logger.info(f"Successfully saved {count} BINs to database")
                return count
            except Exception as e:
                logger.error(f"Error saving BINs to database: {str(e)}")
                session.rollback()
                return 0
            finally:
                session.close()
                engine.dispose()
                
        except Exception as e:
            logger.error(f"Error setting up database session: {str(e)}")
            return 0
            
    def download_and_process_bins(self) -> int:
        """
        Download the BIN database, parse it, and save to the database
        
        Returns:
            Number of BINs saved to the database
        """
        try:
            # Download the BIN database
            csv_path = self.download_bin_database()
            if not csv_path:
                logger.error("Failed to download BIN database")
                return 0
                
            # Parse the CSV file
            bin_data = self.parse_bin_csv(csv_path)
            if not bin_data:
                logger.error("Failed to parse BIN database CSV")
                return 0
                
            # Save the BIN data to the database
            count = self.save_bins_to_database(bin_data)
            
            # Clean up the temporary file
            try:
                os.remove(csv_path)
            except:
                logger.warning(f"Failed to delete temporary file {csv_path}")
                
            return count
            
        except Exception as e:
            logger.error(f"Error in download_and_process_bins: {str(e)}")
            return 0


# Run as standalone script
if __name__ == "__main__":
    from main import app
    
    with app.app_context():
        downloader = BINDownloader()
        bin_count = downloader.download_and_process_bins()
        print(f"Downloaded and processed {bin_count} BINs")
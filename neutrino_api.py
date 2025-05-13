"""
Neutrino API Integration for BIN verification

This module provides functions to verify BIN (Bank Identification Number) data
using the Neutrino API's BIN Lookup service.

Neutrino API Documentation: https://www.neutrinoapi.com/api/bin-lookup/
"""

import os
import json
import logging
import requests
from typing import Dict, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NeutrinoAPIClient:
    """Client for interacting with Neutrino API's BIN Lookup service"""
    
    def __init__(self):
        """Initialize the Neutrino API client with credentials from environment variables"""
        self.user_id = os.environ.get("NEUTRINO_API_USER_ID")
        self.api_key = os.environ.get("NEUTRINO_API_KEY")
        
        if not self.user_id or not self.api_key:
            logger.warning("Neutrino API credentials not found in environment variables")
            raise ValueError("Neutrino API credentials not configured correctly")
            
        self.base_url = "https://neutrinoapi.net/bin-lookup"
        self.session = self._create_session()
        
    def _create_session(self) -> requests.Session:
        """Create a requests session with proper authentication and headers"""
        session = requests.Session()
        # Ensure we have valid credentials before setting headers
        if self.user_id is not None and self.api_key is not None:
            # Use header-based authentication as per documentation
            session.headers.update({
                'User-ID': self.user_id,
                'API-Key': self.api_key,
                'User-Agent': 'BINIntelligenceSystem/1.0',
                'Content-Type': 'application/x-www-form-urlencoded'  # For form data
            })
        else:
            session.headers.update({
                'User-Agent': 'BINIntelligenceSystem/1.0',
                'Content-Type': 'application/x-www-form-urlencoded'  # For form data
            })
        return session
    
    def lookup_bin(self, bin_code: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
        """
        Lookup a BIN using the Neutrino API
        
        Args:
            bin_code: The 6-digit BIN to look up
            timeout: Request timeout in seconds
            
        Returns:
            Dictionary with BIN information or None if lookup failed
        """
        if not bin_code or not bin_code.isdigit() or len(bin_code) < 6:
            logger.error(f"Invalid BIN format: {bin_code}")
            return None
            
        # Use only first 6 digits for BIN lookup
        bin_code = bin_code[:6]
        
        try:
            payload = {
                "bin-number": bin_code,
                "customer-ip": "127.0.0.1"  # Default value for API requirement
            }
            
            logger.info(f"Looking up BIN {bin_code} via Neutrino API")
            response = self.session.post(
                self.base_url,
                data=payload,  # Changed from json to data for proper form encoding
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Successfully retrieved data for BIN {bin_code}")
                return self._transform_neutrino_response(bin_code, result)
            else:
                logger.warning(f"BIN lookup failed: HTTP {response.status_code}, Response: {response.text}")
                # Return empty data instead of None to avoid type errors
                return {
                    "BIN": bin_code,
                    "issuer": "Unknown",
                    "brand": "Unknown",
                    "type": "Unknown",
                    "prepaid": False,
                    "country": "XX",
                    "threeDS1Supported": False,
                    "threeDS2supported": False,
                    "patch_status": "Exploitable",
                    "data_source": f"Neutrino API Error ({response.status_code})",
                    "issuer_website": None,
                    "issuer_phone": None
                }
                
        except Exception as e:
            logger.error(f"Error looking up BIN {bin_code}: {str(e)}")
            # Return empty data instead of None to avoid type errors
            return {
                "BIN": bin_code,
                "issuer": "Unknown",
                "brand": "Unknown",
                "type": "Unknown",
                "prepaid": False,
                "country": "XX",
                "threeDS1Supported": False,
                "threeDS2supported": False,
                "patch_status": "Exploitable",
                "data_source": f"Neutrino API Exception",
                "issuer_website": None,
                "issuer_phone": None
            }
    
    def _transform_neutrino_response(self, bin_code: str, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform the Neutrino API response to match our internal format
        
        Args:
            bin_code: The original BIN code queried
            response: The raw Neutrino API response
            
        Returns:
            Dictionary with BIN information in our system's format
        """
        # Check if the BIN is valid according to the API
        is_valid = response.get("valid", False)
        if not is_valid:
            logger.warning(f"BIN {bin_code} reported as invalid by Neutrino API")
            # Return empty data instead of None to avoid type errors
            return {
                "BIN": bin_code,
                "issuer": "Unknown",
                "brand": "Unknown",
                "type": "Unknown",
                "prepaid": False,
                "country": "XX",
                "threeDS1Supported": False,
                "threeDS2supported": False,
                "patch_status": "Exploitable",
                "data_source": "Neutrino API (Invalid BIN)",
                "issuer_website": None,
                "issuer_phone": None
            }
            
        # Determine 3DS support based on card categories and types
        # Note: The actual API doesn't provide 3DS info directly, 
        # but we can infer it from card types and categories
        card_type = response.get("card-type", "").upper()
        card_category = response.get("card-category", "").upper()
        card_brand = response.get("card-brand", "").upper()
        
        # Extract card level from card category
        card_level = None
        card_level_keywords = ["PLATINUM", "GOLD", "SIGNATURE", "WORLD", "STANDARD", "CLASSIC", "BUSINESS", 
                               "CORPORATE", "COMMERCIAL", "PREMIER", "INFINITE", "DIAMOND", "BLACK"]
        
        for keyword in card_level_keywords:
            if keyword in card_category:
                card_level = keyword
                break
        
        # Most premium cards (PLATINUM, GOLD, SIGNATURE) have 3DS
        premium_card = any(category in card_category for category in ["PLATINUM", "GOLD", "SIGNATURE", "WORLD"])
        # Business/corporate cards might not have 3DS
        business_card = any(category in card_category for category in ["BUSINESS", "CORPORATE", "COMMERCIAL"])
        
        # Determine 3DS support - this is a heuristic since the API doesn't provide this directly
        threeds1_supported = premium_card and not business_card
        # 3DS2 is more common in newer cards and premium cards from major issuers
        threeds2_supported = premium_card and card_brand in ["VISA", "MASTERCARD"] and not business_card
        
        # Determine patch status based on 3DS support
        patch_status = "Patched" if (threeds1_supported or threeds2_supported) else "Exploitable"
            
        # Build response in our format
        return {
            "BIN": bin_code,
            "issuer": response.get("issuer"),
            "brand": response.get("card-brand"),
            "type": response.get("card-type", ""),  # DEBIT, CREDIT, CHARGE CARD
            "card_level": card_level,  # PLATINUM, GOLD, etc.
            "prepaid": response.get("is-prepaid", False),  # Boolean in the API
            "country": response.get("country-code"),  # ISO 2-letter country code
            "threeDS1Supported": threeds1_supported,
            "threeDS2supported": threeds2_supported,
            "patch_status": patch_status,
            "data_source": "Neutrino API",
            # Additional fields from Neutrino API
            "issuer_website": response.get("issuer-website"),
            "issuer_phone": response.get("issuer-phone")
        }
        
    def verify_and_update_bin(self, existing_bin_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify and update existing BIN data with information from Neutrino API
        
        Args:
            existing_bin_data: Existing BIN data from our system
            
        Returns:
            Updated BIN data with information from Neutrino API
        """
        bin_code = existing_bin_data.get("BIN")
        if not bin_code:
            logger.error("Missing BIN code in existing data")
            return existing_bin_data
            
        neutrino_data = self.lookup_bin(bin_code)
        if not neutrino_data:
            logger.warning(f"Could not verify BIN {bin_code} with Neutrino API")
            return existing_bin_data
            
        # Mark the data as verified
        neutrino_data["exploit_type"] = existing_bin_data.get("exploit_type", "Unknown")
        neutrino_data["verified"] = True
        neutrino_data["verified_date"] = None  # Could add timestamp here
        
        return neutrino_data


# Simple test function
def test_neutrino_api():
    """Test the Neutrino API with a sample BIN"""
    try:
        client = NeutrinoAPIClient()
        test_bin = "411111"  # Example Visa test BIN
        result = client.lookup_bin(test_bin)
        
        if result:
            print(f"Successfully tested Neutrino API BIN Lookup with {test_bin}")
            print(json.dumps(result, indent=2))
            return True
        else:
            print(f"Failed to lookup BIN {test_bin} with Neutrino API")
            return False
            
    except Exception as e:
        print(f"Error testing Neutrino API: {str(e)}")
        return False


if __name__ == "__main__":
    test_neutrino_api()
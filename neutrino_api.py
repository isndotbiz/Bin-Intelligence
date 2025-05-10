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
        # Ensure we have valid credentials before setting auth
        if self.user_id is not None and self.api_key is not None:
            # Use HTTPBasicAuth for proper typing
            from requests.auth import HTTPBasicAuth
            session.auth = HTTPBasicAuth(self.user_id, self.api_key)
        
        session.headers.update({
            'User-Agent': 'BINIntelligenceSystem/1.0',
            'Content-Type': 'application/json'
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
                json=payload,
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Successfully retrieved data for BIN {bin_code}")
                return self._transform_neutrino_response(bin_code, result)
            else:
                logger.warning(f"BIN lookup failed: HTTP {response.status_code}, Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error looking up BIN {bin_code}: {str(e)}")
            return None
    
    def _transform_neutrino_response(self, bin_code: str, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform the Neutrino API response to match our internal format
        
        Args:
            bin_code: The original BIN code queried
            response: The raw Neutrino API response
            
        Returns:
            Dictionary with BIN information in our system's format
        """
        # Default values
        is_valid = response.get("valid", False)
        if not is_valid:
            logger.warning(f"BIN {bin_code} reported as invalid by Neutrino API")
            
        # Extract card security info
        security_info = {}
        card_security = response.get("card-security")
        if card_security:
            if "3d-secure" in card_security.lower():
                security_info["threeDS1Supported"] = True
            if "3d-secure 2" in card_security.lower() or "3ds2" in card_security.lower():
                security_info["threeDS2supported"] = True
        
        # Determine patch status based on security measures
        if security_info.get("threeDS2supported") or security_info.get("threeDS1Supported"):
            patch_status = "Patched"
        else:
            patch_status = "Exploitable"
            
        # Build response in our format
        return {
            "BIN": bin_code,
            "issuer": response.get("issuer"),
            "brand": response.get("card-brand"),
            "type": response.get("card-type"),
            "prepaid": response.get("card-category") == "PREPAID",
            "country": response.get("country-code"),
            "threeDS1Supported": security_info.get("threeDS1Supported", False),
            "threeDS2supported": security_info.get("threeDS2supported", False),
            "patch_status": patch_status,
            "data_source": "Neutrino API",
            # Additional fields from Neutrino API that might be useful
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
import logging
import time
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BinEnricher:
    """Class to enrich BIN data with issuer information and 3DS support using Neutrino API"""
    
    # List of allowed card brands - we only want to track these major networks
    ALLOWED_BRANDS = [
        "VISA", "MASTERCARD", "AMERICAN EXPRESS", "DISCOVER",
        "VISA", "MASTERCARD", "AMEX", "DISCOVER"  # Common variations
    ]
    
    def __init__(self):
        """Initialize the BIN enricher"""
        pass
    
    def enrich_bin(self, bin_code: str) -> Optional[Dict[str, Any]]:
        """
        Enrich a BIN with issuer information and 3DS support data using only Neutrino API.
        Only processes BINs from major card networks (3, 4, 5, or 6 series):
        - 3 series for American Express
        - 4 series for Visa
        - 5 series for MasterCard
        - 6 series for Discover
        
        Args:
            bin_code: The 6-digit BIN to enrich
            
        Returns:
            Dictionary with BIN information or None if lookup failed or invalid BIN
        """
        # Valid first digits for major card networks
        valid_first_digits = ['3', '4', '5', '6']
        
        # Validate BIN format
        if not bin_code or not bin_code.isdigit() or len(bin_code) != 6:
            logger.warning(f"Invalid BIN format: {bin_code}")
            return None
        
        # Only process BINs that start with 3, 4, 5, or 6
        if bin_code[0] not in valid_first_digits:
            logger.warning(f"Skipping BIN {bin_code}: not from a major card network (3, 4, 5, 6)")
            return None
            
        # Get real BIN data from Neutrino API
        bin_data = self._get_bin_data_from_neutrinoapi(bin_code)
        
        if not bin_data:
            logger.warning(f"Could not retrieve data for BIN {bin_code} from Neutrino API")
            return None
            
        # Filter out unwanted card brands
        brand = bin_data.get("brand")
        if brand and brand.upper() not in [b.upper() for b in self.ALLOWED_BRANDS]:
            logger.info(f"Skipping BIN {bin_code}: brand '{bin_data.get('brand')}' not in allowed list")
            return None
            
        # Add 3DS support determination based on card brand and issuer
        bin_data["threeDS1Supported"] = self._check_3ds1_support(bin_code, bin_data)
        bin_data["threeDS2supported"] = self._check_3ds2_support(bin_code, bin_data)
        
        # Determine patch status based on 3DS support
        bin_data["patch_status"] = self._determine_patch_status(
            bin_data["threeDS1Supported"], 
            bin_data["threeDS2supported"]
        )
        
        return bin_data
    
    def _get_bin_data_from_neutrinoapi(self, bin_code: str) -> Optional[Dict[str, Any]]:
        """
        Get real BIN data from Neutrino API - no synthetic fallbacks
        
        Args:
            bin_code: The 6-digit BIN to look up
            
        Returns:
            Dictionary with real BIN information or None if lookup failed
        """
        try:
            from neutrino_api import NeutrinoAPIClient
            
            # Add a minimal delay to avoid hitting rate limits
            time.sleep(0.1)
            
            client = NeutrinoAPIClient()
            bin_data = client.lookup_bin(bin_code)
            
            if bin_data:
                logger.info(f"Successfully retrieved real data for BIN {bin_code} from Neutrino API")
                return bin_data
            else:
                logger.warning(f"Could not retrieve data for BIN {bin_code} from Neutrino API")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving data for BIN {bin_code} from Neutrino API: {str(e)}")
            return None
    
    def _check_3ds1_support(self, bin_code: str, bin_data: Dict[str, Any]) -> bool:
        """
        Check if the BIN supports 3DS version 1 based on card data
        
        Args:
            bin_code: The BIN number
            bin_data: The BIN data from Neutrino API
            
        Returns:
            Boolean indicating 3DS1 support
        """
        # In a real implementation, this would query a 3DS directory service
        # For now, we'll make educated guesses based on known patterns and card data
        
        # Most major issuing banks support 3DS v1
        brand = bin_data.get("brand", "").upper()
        issuer = bin_data.get("issuer", "").upper()
        country = bin_data.get("country", "").upper()
        
        # Default rules - these could be enhanced with real 3DS directory data
        if brand in ["VISA", "MASTERCARD"] and country in ["US", "GB", "CA", "AU", "DE", "FR"]:
            return True
        elif brand == "AMERICAN EXPRESS" or brand == "AMEX":
            return True
        elif "CREDIT" in bin_data.get("type", "").upper():
            return True
        else:
            # Default to not supported
            return False
    
    def _check_3ds2_support(self, bin_code: str, bin_data: Dict[str, Any]) -> bool:
        """
        Check if the BIN supports 3DS version 2 based on card data
        
        Args:
            bin_code: The BIN number
            bin_data: The BIN data from Neutrino API
            
        Returns:
            Boolean indicating 3DS2 support
        """
        # In a real implementation, this would query a 3DS directory service
        # 3DS v2 is newer, so we'll be more conservative with our estimates
        
        brand = bin_data.get("brand", "").upper()
        issuer = bin_data.get("issuer", "").upper()
        country = bin_data.get("country", "").upper()
        
        # Major US and EU issuers have been early adopters of 3DS2
        if brand in ["VISA", "MASTERCARD"] and country in ["US", "GB", "DE", "FR"]:
            return True
        else:
            # Default to not supported
            return False
    
    def _determine_patch_status(self, threeDS1Supported: bool, threeDS2supported: bool) -> str:
        """
        Determine the patch status based on 3DS support
        
        Args:
            threeDS1Supported: Whether 3DS v1 is supported
            threeDS2supported: Whether 3DS v2 is supported
            
        Returns:
            "Patched" or "Exploitable"
        """
        if threeDS1Supported or threeDS2supported:
            return "Patched"
        else:
            return "Exploitable"
            
    def enrich_bins_batch(self, bin_codes: List[str]) -> List[Dict[str, Any]]:
        """
        Enrich a batch of BINs with real data from Neutrino API
        
        Args:
            bin_codes: List of BIN codes to enrich
            
        Returns:
            List of enriched BIN data dictionaries (only valid, allowed BINs)
        """
        enriched_bins = []
        
        for bin_code in bin_codes:
            bin_data = self.enrich_bin(bin_code)
            if bin_data:
                enriched_bins.append(bin_data)
                
        return enriched_bins

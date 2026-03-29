import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BinEnricher:
    """Class to enrich BIN data with issuer information and 3DS support.

    Uses Adyen BinLookup API for real 3DS enrollment data when available,
    falls back to heuristic inference when Adyen credentials are not configured.
    Neutrino API provides supplementary metadata (issuer, brand, country).
    """

    # List of allowed card brands - we only want to track these major networks
    ALLOWED_BRANDS = [
        "VISA", "MASTERCARD", "AMERICAN EXPRESS", "AMEX", "DISCOVER"
    ]

    CACHE_FILE = "adyen_3ds_cache.json"
    CACHE_TTL_DAYS = 30

    def __init__(self):
        """Initialize the BIN enricher with Adyen client for real 3DS data"""
        from adyen_client import AdyenBinLookupClient
        self._adyen = AdyenBinLookupClient()
        self._use_adyen = self._adyen.available

        # Initialize Neutrino client once (reuse session across all lookups)
        from neutrino_api import NeutrinoAPIClient
        try:
            self._neutrino = NeutrinoAPIClient()
        except ValueError:
            self._neutrino = None

        # Load 3DS cache from disk
        self._3ds_cache = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        """Load Adyen 3DS results cache from disk."""
        try:
            if os.path.exists(self.CACHE_FILE):
                with open(self.CACHE_FILE, 'r') as f:
                    cache = json.load(f)
                logger.info(f"Loaded {len(cache)} cached 3DS results from {self.CACHE_FILE}")
                return cache
        except Exception as e:
            logger.warning(f"Failed to load 3DS cache: {e}")
        return {}

    def _save_cache(self):
        """Persist Adyen 3DS results cache to disk."""
        try:
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(self._3ds_cache, f)
        except Exception as e:
            logger.warning(f"Failed to save 3DS cache: {e}")

    def _get_cached_3ds(self, bin_code: str) -> Optional[Dict[str, Any]]:
        """Return cached Adyen 3DS result if fresh (within TTL)."""
        entry = self._3ds_cache.get(bin_code)
        if not entry:
            return None
        cached_at = datetime.fromisoformat(entry.get("cached_at", "2000-01-01"))
        if datetime.utcnow() - cached_at > timedelta(days=self.CACHE_TTL_DAYS):
            return None
        return entry

    def _cache_3ds(self, bin_code: str, data: Dict[str, Any]):
        """Store Adyen 3DS result in cache with timestamp."""
        data["cached_at"] = datetime.utcnow().isoformat()
        self._3ds_cache[bin_code] = data
        self._save_cache()
    
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
            
        # Get 3DS data: check cache first, then Adyen API, then heuristic fallback
        adyen_data = self._get_cached_3ds(bin_code)
        if adyen_data:
            logger.debug(f"Using cached 3DS data for BIN {bin_code}")
        elif self._use_adyen:
            adyen_data = self._adyen.get_3ds_availability(bin_code)
            if adyen_data:
                self._cache_3ds(bin_code, adyen_data)

        if adyen_data:
            bin_data["threeDS1Supported"] = adyen_data["threeDS1Supported"]
            bin_data["threeDS2supported"] = adyen_data["threeDS2supported"]
            bin_data["auto3DSSupported"] = adyen_data.get("auto3DSSupported", False)
            bin_data["threeds_data_source"] = "adyen"
        else:
            # Heuristic fallback when Adyen is not available
            bin_data["threeDS1Supported"] = self._check_3ds1_support_heuristic(bin_code, bin_data)
            bin_data["threeDS2supported"] = self._check_3ds2_support_heuristic(bin_code, bin_data)
            bin_data["auto3DSSupported"] = self._check_auto_3ds_support_heuristic(bin_code, bin_data, bin_data["threeDS2supported"])
            bin_data["threeds_data_source"] = "heuristic"

        # Determine patch status based on 3DS support
        bin_data["patch_status"] = self._determine_patch_status(
            bin_data["threeDS1Supported"],
            bin_data["threeDS2supported"]
        )

        # Determine the exploit type based on 3DS and Auto 3DS support
        if not bin_data["auto3DSSupported"]:
            bin_data["exploit_type"] = "no-auto-3ds"
        else:
            bin_data["exploit_type"] = "card-not-present"

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
            if not self._neutrino:
                logger.warning(f"Neutrino API not configured, cannot look up BIN {bin_code}")
                return None

            # Add a minimal delay to avoid hitting rate limits
            time.sleep(0.1)

            bin_data = self._neutrino.lookup_bin(bin_code)
            
            if bin_data:
                logger.info(f"Successfully retrieved real data for BIN {bin_code} from Neutrino API")
                return bin_data
            else:
                logger.warning(f"Could not retrieve data for BIN {bin_code} from Neutrino API")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving data for BIN {bin_code} from Neutrino API: {str(e)}")
            return None
    
    def _check_3ds1_support_heuristic(self, bin_code: str, bin_data: Dict[str, Any]) -> bool:
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
    
    def _check_3ds2_support_heuristic(self, bin_code: str, bin_data: Dict[str, Any]) -> bool:
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
    
    def _check_auto_3ds_support_heuristic(self, bin_code: str, bin_data: Dict[str, Any], threeds2_precomputed: bool = None) -> bool:
        """
        Check if the BIN supports automatic 3DS authentication without user intervention
        
        Args:
            bin_code: The BIN number
            bin_data: The BIN data from Neutrino API
            
        Returns:
            Boolean indicating Auto 3DS support
        """
        # Get relevant data
        brand = bin_data.get("brand", "").upper()
        issuer = bin_data.get("issuer", "").upper()
        country = bin_data.get("country", "").upper()
        threeds2_supported = threeds2_precomputed if threeds2_precomputed is not None else self._check_3ds2_support_heuristic(bin_code, bin_data)
        
        # Auto 3DS is only available with 3DS2, so that's a prerequisite
        if not threeds2_supported:
            return False
            
        # Determine Auto 3DS support based on real-world adoption patterns
        # Major issuers in specific countries have implemented the frictionless flow
        major_issuers_with_auto_3ds = [
            "CHASE", "BANK OF AMERICA", "CAPITAL ONE", "JPMORGAN", "CITI", "BARCLAYS",
            "HSBC", "DEUTSCHE BANK", "BNP PARIBAS", "SANTANDER", "RBC", "SCOTIA",
            "COMMONWEALTH BANK", "ANZ", "LLOYDS", "ROYAL BANK", "AMEX", "AMERICAN EXPRESS"
        ]
        
        # Check if any major issuer name appears in the issuer field
        issuer_supports_auto_3ds = any(major_issuer in issuer for major_issuer in major_issuers_with_auto_3ds)
        
        # Check combination of brand, country and issuer support
        if brand in ["VISA", "MASTERCARD"] and country in ["US", "GB", "DE", "FR", "CA", "AU"] and issuer_supports_auto_3ds:
            return True
        elif brand == "AMERICAN EXPRESS" and country in ["US", "GB"]:
            return True  # Amex generally has good Auto 3DS implementation
            
        # Default to no Auto 3DS support
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

"""
Adyen BinLookup API Integration for 3DS Enrollment Data

Uses Adyen's get3dsAvailability endpoint to determine real 3DS enrollment
status for BINs, replacing heuristic-based guessing.

Adyen API Docs: https://docs.adyen.com/api-explorer/BinLookup/54/post/get3dsAvailability
"""

import os
import logging
import requests
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AdyenBinLookupClient:
    """Client for Adyen BinLookup API — get3dsAvailability endpoint"""

    BASE_URL = "https://pal-live.adyen.com/pal/servlet/BinLookup/v54"
    TEST_URL = "https://pal-test.adyen.com/pal/servlet/BinLookup/v54"

    def __init__(self):
        self.api_key = os.environ.get("ADYEN_API_KEY")
        self.merchant_account = os.environ.get("ADYEN_MERCHANT_ACCOUNT")
        self.use_test = os.environ.get("ADYEN_USE_TEST", "true").lower() == "true"

        if not self.api_key or not self.merchant_account:
            logger.warning("Adyen credentials not configured (ADYEN_API_KEY, ADYEN_MERCHANT_ACCOUNT)")
            self.available = False
        else:
            self.available = True
            self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "BINIntelligenceSystem/2.3.0"
        })
        return session

    @property
    def _base_url(self) -> str:
        return self.TEST_URL if self.use_test else self.BASE_URL

    def get_3ds_availability(self, bin_code: str) -> Optional[Dict[str, Any]]:
        """
        Check 3DS availability for a BIN using Adyen's BinLookup API.

        Args:
            bin_code: 6-digit BIN to check

        Returns:
            Dict with threeDS1Supported, threeDS2supported, data_source fields,
            or None if lookup failed or client not configured.
        """
        if not self.available:
            return None

        if not bin_code or not bin_code.isdigit() or len(bin_code) < 6:
            logger.warning(f"Invalid BIN format for Adyen lookup: {bin_code}")
            return None

        bin_code = bin_code[:6]

        try:
            payload = {
                "merchantAccount": self.merchant_account,
                "cardNumber": bin_code + "0000000000",  # Pad to 16 digits for API
                "brands": ["visa", "mc", "amex", "discover"]
            }

            url = f"{self._base_url}/get3dsAvailability"
            logger.info(f"Checking 3DS availability for BIN {bin_code} via Adyen")

            response = self.session.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                result = response.json()
                return self._parse_response(bin_code, result)
            else:
                logger.warning(f"Adyen 3DS lookup failed for BIN {bin_code}: HTTP {response.status_code}")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Adyen API timeout for BIN {bin_code}")
            return None
        except Exception as e:
            logger.error(f"Adyen API error for BIN {bin_code}: {str(e)}")
            return None

    def _parse_response(self, bin_code: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Adyen get3dsAvailability response into our format."""
        threeds1 = False
        threeds2 = False

        # Check threeDS1 availability
        if result.get("threeDS1Supported"):
            threeds1 = True

        # Check threeDS2 availability — look at threeDS2CardRangeDetail
        threeds2_details = result.get("threeDS2CardRangeDetail", [])
        if threeds2_details:
            threeds2 = True
        elif result.get("threeDS2supported"):
            threeds2 = True

        logger.info(f"Adyen 3DS result for BIN {bin_code}: 3DS1={threeds1}, 3DS2={threeds2}")

        return {
            "threeDS1Supported": threeds1,
            "threeDS2supported": threeds2,
            "data_source": "adyen",
            "auto3DSSupported": threeds2  # 3DS2 implies frictionless capability
        }

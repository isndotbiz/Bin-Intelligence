import re
import logging
import time
from collections import Counter, defaultdict
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Tuple, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define keyword to exploit type mapping - focus only on CNP for e-commerce
KEYWORD_TO_EXPLOIT_TYPE = {
    # Card-not-present related keywords
    "cnp": "card-not-present",
    "ecom": "card-not-present",
    "online": "card-not-present",
    "shop": "card-not-present",
    "checkout": "card-not-present",
    "purchase": "card-not-present",
    "merchant": "card-not-present",
    "authorization": "card-not-present",
    "payment": "card-not-present",
    "gateway": "card-not-present",
    "digital": "card-not-present",
    "internet": "card-not-present",
    "web": "card-not-present",
    "processor": "card-not-present",
    "transaction": "card-not-present",
    "website": "card-not-present",
    "virtual": "card-not-present"
}

# PAN regex pattern - matches credit card numbers with optional separators
PAN_PATTERN = re.compile(r'(?:\d[ -]*?){13,16}')

# BIN extraction - gets first 6 digits from a PAN
BIN_PATTERN = re.compile(r'^\D*?(\d{6})')

class FraudFeedScraper:
    def __init__(self, timeout=5):
        """Initialize the fraud feed scraper with retry mechanism"""
        self.timeout = timeout
        self.session = self._create_session_with_retries()
        
    def _create_session_with_retries(self) -> requests.Session:
        """Create a requests session with retry mechanism"""
        session = requests.Session()
        
        # Configure retry strategy
        retries = Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        
        # Add the retry adapter to session
        adapter = HTTPAdapter(max_retries=retries)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        return session
    
    def _extract_pans(self, text: str) -> List[str]:
        """Extract potential PANs from text using regex"""
        pans = []
        matches = PAN_PATTERN.findall(text)
        for match in matches:
            # Clean the PAN by removing spaces and dashes
            clean_pan = re.sub(r'[ -]', '', match)
            # Validate using Luhn algorithm and length check
            if self._is_valid_pan(clean_pan):
                pans.append(clean_pan)
        return pans
    
    def _is_valid_pan(self, pan: str) -> bool:
        """
        Validate a PAN using the Luhn algorithm and length check
        """
        # Check if it's a proper length for a credit card number (13-19 digits)
        if not re.match(r'^\d{13,19}$', pan):
            return False
            
        # Luhn algorithm validation
        check_sum = 0
        num_digits = len(pan)
        odd_even = num_digits & 1
        
        for i in range(num_digits):
            digit = int(pan[i])
            if ((i & 1) ^ odd_even) == 0:
                digit *= 2
                if digit > 9:
                    digit -= 9
            check_sum += digit
            
        return (check_sum % 10) == 0
    
    def _extract_bin(self, pan: str) -> Optional[str]:
        """Extract the BIN (first 6 digits) from a PAN"""
        match = BIN_PATTERN.match(pan)
        if match:
            return match.group(1)
        return None
    
    def _detect_exploit_type(self, text: str) -> Optional[str]:
        """
        Detect the exploit type based on keywords in the text
        Returns the most frequent exploit type or None if no keywords found
        """
        text_lower = text.lower()
        exploit_types = []
        
        for keyword, exploit_type in KEYWORD_TO_EXPLOIT_TYPE.items():
            if keyword.lower() in text_lower:
                exploit_types.append(exploit_type)
        
        if not exploit_types:
            return None
        
        # Return the most common exploit type
        return Counter(exploit_types).most_common(1)[0][0]

    def scrape_pastebin(self, sample_pages=5) -> List[Tuple[str, str, str]]:
        """
        Scrape Pastebin for recent public pastes that might contain credit card data
        Returns: List of tuples (paste_id, paste_title, paste_text)
        """
        pastes = []
        
        try:
            # Scrape the Pastebin archive page
            logger.info(f"Scraping Pastebin recent pastes, sample pages: {sample_pages}")
            archive_url = "https://pastebin.com/archive"
            response = self.session.get(archive_url, timeout=self.timeout)
            response.raise_for_status()
            
            # Extract paste IDs from the archive page
            paste_ids = re.findall(r'<a[^>]+href="/([a-zA-Z0-9]{8})"[^>]*>', response.text)
            
            # Limit to the requested number of pastes
            paste_ids = paste_ids[:sample_pages]
            
            # Scrape each paste
            for paste_id in paste_ids:
                try:
                    # Add a small delay to avoid being rate-limited
                    time.sleep(1)
                    
                    paste_url = f"https://pastebin.com/raw/{paste_id}"
                    logger.debug(f"Scraping paste: {paste_url}")
                    
                    response = self.session.get(paste_url, timeout=self.timeout)
                    if response.status_code == 200:
                        paste_text = response.text
                        paste_title = f"Paste {paste_id}"
                        pastes.append((paste_id, paste_title, paste_text))
                        logger.debug(f"Successfully scraped paste {paste_id}")
                    else:
                        logger.warning(f"Failed to scrape paste {paste_id}: HTTP {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"Error scraping paste {paste_id}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error scraping Pastebin archive: {str(e)}")
            
        logger.info(f"Scraped {len(pastes)} pastes from Pastebin")
        return pastes

    def _handle_no_data_found(self) -> List[Tuple[str, str]]:
        """
        Handle the case when no real data is found from feeds.
        We don't generate synthetic data anymore, only return an empty list.
        
        Returns:
            Empty list - we only want real-world data
        """
        logger.warning("No real BINs found from data feeds. No synthetic data will be generated.")
        return []
        
    def fetch_exploited_bins(self, top_n=100, sample_pages=5) -> List[Tuple[str, str]]:
        """
        Fetch exploited BINs from public card-dump feeds and classify exploit types.
        Only include BINs from major card networks (3, 4, 5, or 6 series):
        - 3 series for American Express
        - 4 series for Visa
        - 5 series for MasterCard
        - 6 series for Discover
        
        Args:
            top_n: Number of top BINs to return
            sample_pages: Number of pages/posts to sample from each source
            
        Returns:
            List of tuples (bin, exploit_type) sorted by frequency
        """
        # Dictionary to store BIN to keywords mapping
        bin_keywords: Dict[str, list] = defaultdict(list)
        
        # Dictionary to store BIN frequencies
        bin_counter = Counter()
        
        # Scrape Pastebin
        pastes = self.scrape_pastebin(sample_pages)
        
        # Valid first digits for major card networks
        valid_first_digits = ['3', '4', '5', '6']
        
        for paste_id, paste_title, paste_text in pastes:
            # Extract PANs from paste
            pans = self._extract_pans(paste_text)
            
            # Extract exploit type from paste text
            exploit_type = self._detect_exploit_type(paste_text)
            
            for pan in pans:
                bin_code = self._extract_bin(pan)
                # Only include BINs that start with 3, 4, 5, or 6
                if bin_code and bin_code[0] in valid_first_digits:
                    bin_counter[bin_code] += 1
                    if exploit_type:
                        bin_keywords[bin_code].append(exploit_type)
        
        # Get the most common exploit type for each BIN
        bin_exploit_types = []
        for bin_code, count in bin_counter.most_common(top_n):
            # Get the most common exploit type for this BIN
            exploit_types = bin_keywords.get(bin_code, [])
            if exploit_types:
                most_common_exploit = Counter(exploit_types).most_common(1)[0][0]
                bin_exploit_types.append((bin_code, most_common_exploit))
            else:
                bin_exploit_types.append((bin_code, None))
        
        # Log the results
        total_bins = len(bin_exploit_types)
        classified_bins = sum(1 for bin_code, exploit_type in bin_exploit_types if exploit_type)
        
        logger.info(f"Fetched {total_bins} exploited BINs, {classified_bins} with classification")
        logger.info(f"Top 10 BINs by frequency: {bin_counter.most_common(10)}")
        
        # If no real data was found, handle it appropriately (no synthetic data)
        if not bin_exploit_types:
            bin_exploit_types = self._handle_no_data_found()
        
        return bin_exploit_types

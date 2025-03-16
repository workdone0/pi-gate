import sys
import requests
import logging
import os
import time
import pickle
import re
from pathlib import Path
from typing import Optional, List, Tuple
from pybloom_live import BloomFilter
from urllib.parse import urlparse

class BlmFilter:
    """
    A class to efficiently load and check URLs using a Bloom filter.
    Designed for resource-constrained environments like Raspberry Pi.
    """
    
    BLOOM_FILTER_PATH = Path("/tmp/bloom_filter.pkl")
    LOG_FILE = Path("/tmp/bloom.log")
    
    def __init__(self, expected_entries: int = 600000, error_rate: float = 0.001):
        """
        Initialize the URL blocker with bloom filter parameters.
        
        Args:
            expected_entries: The expected number of URLs to be loaded
            error_rate: Acceptable false positive rate (0.001 = 0.1%)
        """
        self.expected_entries = expected_entries
        self.error_rate = error_rate
        self.bloom_filter = None
        self.setup_logging()
        
    def setup_logging(self) -> None:
        """Configure logging to file and console."""
        try:
            # Ensure the log directory exists
            os.makedirs(os.path.dirname(self.LOG_FILE), exist_ok=True)
            
            # Check if we can write to the log file
            try:
                with open(self.LOG_FILE, 'a') as f:
                    pass
            except PermissionError:
                # Fall back to a user-accessible location if /tmp is not writable
                self.LOG_FILE = Path(os.path.expanduser("~/pi_gate.log"))
                print(f"Warning: Cannot write to /tmp/pi_gate.log, using {self.LOG_FILE} instead")
            
            # Create a logger specifically for this class
            self.logger = logging.getLogger('BloomFilter')
            
            # Clear any existing handlers to avoid duplicates
            if self.logger.handlers:
                self.logger.handlers.clear()
            
            # Set the level for this logger
            self.logger.setLevel(logging.INFO)
            
            # Create formatter
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            
            # Add file handler
            file_handler = logging.FileHandler(self.LOG_FILE, mode='a')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            
            # Set propagate to False to prevent messages from propagating to the root logger
            self.logger.propagate = False
            
            self.logger.info("BloomFilter logging initialized")
        except Exception as e:
            print(f"Error setting up logging: {e}")
            

    
    def normalize_url(self, url: str) -> str:
        """
        Normalize a URL to ensure consistent format for checking.
        
        Args:
            url: The URL to normalize
            
        Returns:
            Normalized URL string
        """
        # Remove protocol, 'www.', trailing slashes, and convert to lowercase
        url = url.lower().strip()
        
        # Handle common URL formats
        if '://' in url:
            parsed = urlparse(url)
            url = parsed.netloc
        
        # Remove 'www.' prefix if present
        if url.startswith('www.'):
            url = url[4:]
            
        # Remove trailing slashes and whitespace
        url = url.rstrip('/')
        
        return url
    
    def load_urls_from_url(self, url: str) -> Tuple[bool, str]:
        """
        Load URLs from a remote URL into a Bloom filter.
        
        Args:
            url: URL of the list to download
            
        Returns:
            Tuple of (success, message)
        """
        self.logger.info(f"Starting to load URLs from {url}")
        start_time = time.time()
        
        # Create a new Bloom filter
        bloom = BloomFilter(capacity=self.expected_entries, error_rate=self.error_rate)
        
        try:
            # Stream the file to process it line by line
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            count = 0
            for line in response.iter_lines():
                if line:
                    # Convert bytes to string and strip whitespace
                    url_entry = line.decode('utf-8', errors='ignore').strip()
                    
                    # Skip comment lines and empty lines
                    if not url_entry or url_entry.startswith('#'):
                        continue
                    
                    # Handle different formats of blocklist entries
                    # Format: "0.0.0.0 domain.com" or "127.0.0.1 domain.com"
                    if re.match(r'^\d+\.\d+\.\d+\.\d+\s+', url_entry):
                        url_entry = url_entry.split()[1]
                    # Format: "domain.com"
                    elif ' ' in url_entry:
                        url_entry = url_entry.split()[0]
                    
                    # Normalize the URL before adding to the filter
                    normalized_url = self.normalize_url(url_entry)
                    if normalized_url:  # Only add non-empty URLs
                        bloom.add(normalized_url)
                        count += 1
                    
                    # Log progress periodically
                    if count % 50000 == 0:
                        self.logger.info(f"Processed {count} entries...")
            
            elapsed_time = time.time() - start_time
            memory_usage = bloom.bitarray.nbytes / (1024*1024)
            
            self.logger.info(f"Loaded {count} URLs in {elapsed_time:.2f} seconds")
            self.logger.info(f"Bloom filter memory usage: {memory_usage:.2f} MB")
            
            # Save sample entries for debugging
            if count > 0:
                self.logger.info(f"Sample entry format: {normalized_url}")
            
            self.bloom_filter = bloom
            
            # Save to disk for later loading
            self._save_bloom_filter()
            
            return True, f"Successfully loaded {count} URLs"
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Error downloading URL list: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error loading URLs: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def _save_bloom_filter(self) -> bool:
        """Save the bloom filter to disk."""
        try:
            with open(self.BLOOM_FILTER_PATH, 'wb') as f:
                pickle.dump(self.bloom_filter, f)
            self.logger.info(f"Saved bloom filter to {self.BLOOM_FILTER_PATH}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save bloom filter: {str(e)}")
            return False
    
    def load_bloom_filter(self) -> bool:
        """Load the bloom filter from disk if available."""
        try:
            if self.BLOOM_FILTER_PATH.exists():
                with open(self.BLOOM_FILTER_PATH, 'rb') as f:
                    self.bloom_filter = pickle.load(f)
                self.logger.info(f"Loaded bloom filter from {self.BLOOM_FILTER_PATH}")
                self.logger.info(f"Bloom filter contains ~{len(self.bloom_filter)} URLs")
                return True
            else:
                self.logger.warning("No saved bloom filter found.")
                return False
        except Exception as e:
            self.logger.error(f"Failed to load bloom filter: {str(e)}")
            return False
    
    def check_url(self, url: str) -> bool:
        """
        Check if a URL is in the bloom filter (and thus blocked).
        
        Args:
            url: URL to check
            
        Returns:
            True if URL is in the filter, False otherwise
        """
        if self.bloom_filter is None:
            self.logger.error("Bloom filter not initialized. Please load URLs first.")
            return False
        if url.endswith('.'):
            url = url[:-1]
        # Normalize the URL before checking
        normalized_url = self.normalize_url(url)
        return normalized_url in self.bloom_filter
    
    def batch_check_urls(self, urls: List[str]) -> List[Tuple[str, bool]]:
        """
        Check multiple URLs against the bloom filter.
        
        Args:
            urls: List of URLs to check
            
        Returns:
            List of tuples (url, is_blocked)
        """
        if self.bloom_filter is None:
            self.logger.error("Bloom filter not initialized. Please load URLs first.")
            return [(url, False) for url in urls]
        
        return [(url, self.check_url(url)) for url in urls]
    
    def debug_check(self, url: str) -> None:
        """
        Debug function to help troubleshoot false negatives.
        
        Args:
            url: URL to check
        """
        if self.bloom_filter is None:
            self.logger.error("Bloom filter not initialized.")
            return
        
        original_url = url
        normalized_url = self.normalize_url(url)
        result = normalized_url in self.bloom_filter
        
        self.logger.info(f"Debug Check:")
        self.logger.info(f"  Original URL: '{original_url}'")
        self.logger.info(f"  Normalized URL: '{normalized_url}'")
        self.logger.info(f"  In bloom filter: {result}")
        self.logger.info(f"  Bloom filter size: ~{len(self.bloom_filter)} entries")
        self.logger.info(f"  False positive rate: {self.bloom_filter.error_rate}")

# Example of how to use this at boot time
def initialize_bloom(blocklist_url: str) -> Optional[BlmFilter]:
    """
    Initialize the URL blocker at boot time.
    
    Args:
        blocklist_url: URL to download the blocklist from
        
    Returns:
        URLBlocker instance or None if initialization failed
    """
    try:
        blocker = BlmFilter()
        blocker.setup_logging()
        # Try to load existing bloom filter first
        if blocker.load_bloom_filter():
            return blocker
        
        # If loading failed, download and create a new one
        success, message = blocker.load_urls_from_url(blocklist_url)
        if success:
            return blocker
        else:
            logging.error(f"Failed to initialize URL blocker: {message}")
            return None
    except Exception as e:
        logging.error(f"Unexpected error initializing URL blocker: {str(e)}")
        return None


# Testing Code Bloom Filter
"""
if __name__ == "__main__":
    # URL of the blocklist
    blocklist_url = "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/hosts/pro.txt"
    
    # Initialize blocker
    blocker = initialize_bloom(blocklist_url)
    
    if blocker:
        # Example of checking URLs
        test_urls = [
            "example.com",
            "google.com",
            "malicious-domain-example.com",
            # Testing different formats of the same domain to ensure normalization works
            "www.example.com",
            "http://example.com",
            "https://example.com/",
            "EXAMPLE.com",
            "www.0fb.info",
            "analytics.lune-itsolutions.de"
        ]
        
        # Debug individual URLs
        for url in test_urls:
            blocker.debug_check(url)
        
        # # Batch check
        # results = blocker.batch_check_urls(test_urls)
        # for url, is_blocked in results:
        #     print(f"{url} is {'blocked' if is_blocked else 'allowed'}")
    else:
        print("Failed to initialize URL blocker")
"""

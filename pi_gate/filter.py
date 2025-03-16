import requests
import logging
import os
import time
import pickle
from pathlib import Path
from typing import Optional, List, Tuple
from pybloom_live import BloomFilter

class URLBlocker:
    """
    A class to efficiently load and check URLs using a Bloom filter.
    Designed for resource-constrained environments like Raspberry Pi.
    """
    
    BLOOM_FILTER_PATH = Path("/tmp/bloom_filter.pkl")
    LOG_FILE = Path("/tmp/pi_gate.log")
    
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
            # Create directory for log file if it doesn't exist
            self.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            # Set up logging configuration
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(self.LOG_FILE),
                    logging.StreamHandler()
                ]
            )
            self.logger = logging.getLogger('URLBlocker')
        except Exception as e:
            print(f"Failed to set up logging: {str(e)}")
            # Fallback to basic logger
            self.logger = logging.getLogger('URLBlocker')
            self.logger.setLevel(logging.INFO)
    
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
                    
                    # If line has format "IP domain", extract just the domain
                    if ' ' in url_entry:
                        parts = url_entry.split()
                        url_entry = parts[-1]
                    
                    # Add to bloom filter
                    bloom.add(url_entry)
                    count += 1
                    
                    # Log progress periodically
                    if count % 50000 == 0:
                        self.logger.info(f"Processed {count} entries...")
            
            elapsed_time = time.time() - start_time
            memory_usage = bloom.bitarray.nbytes / (1024*1024)
            
            self.logger.info(f"Loaded {count} URLs in {elapsed_time:.2f} seconds")
            self.logger.info(f"Bloom filter memory usage: {memory_usage:.2f} MB")
            
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
        
        return url in self.bloom_filter
    
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
        
        return [(url, url in self.bloom_filter) for url in urls]
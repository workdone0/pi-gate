import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from tempfile import gettempdir

@dataclass
class Config:
    """Centralized configuration for pi-gate"""
    
    # Service configuration
    dns_listen_host: str = "0.0.0.0"
    dns_listen_port: int = 53
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8050
    upstream_dns: tuple = ("8.8.8.8", 53)
    sinkhole_ip: str = "0.0.0.0"
    
    # File paths
    pid_file: Path = field(default_factory=lambda: Path(gettempdir()) / "pi_gate.pid")
    log_file: Path = field(default_factory=lambda: Path(gettempdir()) / "pi_gate.log")
    database_file: Path = field(default_factory=lambda: Path("dns_logs.db"))
    bloom_filter_file: Path = field(default_factory=lambda: Path(gettempdir()) / "bloom_filter.pkl")
    
    # Blocklist configuration
    default_blocklist_url: str = "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/hosts/pro.txt"
    bloom_expected_entries: int = 600000
    bloom_error_rate: float = 0.001
    
    # Dashboard configuration
    dashboard_refresh_interval: int = 5000  # milliseconds
    dashboard_max_logs: int = 1000
    
    # DNS server configuration
    dns_timeout: float = 2.0  # seconds
    dns_max_workers: int = 20
    
    # Logging configuration
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_date_format: str = "%Y-%m-%d %H:%M:%S"
    
    def __post_init__(self):
        """Ensure directories exist and convert strings to Paths"""
        # Convert string paths to Path objects if needed
        if isinstance(self.pid_file, str):
            self.pid_file = Path(self.pid_file)
        if isinstance(self.log_file, str):
            self.log_file = Path(self.log_file)
        if isinstance(self.database_file, str):
            self.database_file = Path(self.database_file)
        if isinstance(self.bloom_filter_file, str):
            self.bloom_filter_file = Path(self.bloom_filter_file)
        
        # Ensure log directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Create config from environment variables"""
        config = cls()
        
        # Override with environment variables if present
        if os.getenv('PI_GATE_DNS_HOST'):
            config.dns_listen_host = os.getenv('PI_GATE_DNS_HOST')
        if os.getenv('PI_GATE_DNS_PORT'):
            config.dns_listen_port = int(os.getenv('PI_GATE_DNS_PORT'))
        if os.getenv('PI_GATE_DASHBOARD_HOST'):
            config.dashboard_host = os.getenv('PI_GATE_DASHBOARD_HOST')
        if os.getenv('PI_GATE_DASHBOARD_PORT'):
            config.dashboard_port = int(os.getenv('PI_GATE_DASHBOARD_PORT'))
        if os.getenv('PI_GATE_UPSTREAM_DNS'):
            upstream = os.getenv('PI_GATE_UPSTREAM_DNS').split(':')
            config.upstream_dns = (upstream[0], int(upstream[1]) if len(upstream) > 1 else 53)
        if os.getenv('PI_GATE_BLOCKLIST_URL'):
            config.default_blocklist_url = os.getenv('PI_GATE_BLOCKLIST_URL')
        if os.getenv('PI_GATE_LOG_LEVEL'):
            config.log_level = os.getenv('PI_GATE_LOG_LEVEL')
        
        return config

def setup_logging(config: Config, logger_name: str = "pi_gate") -> logging.Logger:
    """Set up logging with consistent configuration"""
    logger = logging.getLogger(logger_name)
    
    # Clear existing handlers to avoid duplicates
    if logger.handlers:
        logger.handlers.clear()
    
    # Set log level
    logger.setLevel(getattr(logging, config.log_level.upper()))
    
    # Create formatter
    formatter = logging.Formatter(config.log_format, datefmt=config.log_date_format)
    
    # Add file handler
    try:
        file_handler = logging.FileHandler(config.log_file, mode='a')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except PermissionError:
        # Fallback to user home directory if /tmp is not writable
        fallback_log = Path.home() / "pi_gate.log"
        file_handler = logging.FileHandler(fallback_log, mode='a')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.warning(f"Cannot write to {config.log_file}, using {fallback_log} instead")
    
    # Add console handler for important messages
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)  # Only show warnings and errors on console
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger

# Global config instance
config = Config.from_env() 
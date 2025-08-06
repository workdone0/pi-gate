# pi-gate: A Lightweight DNS Sinkhole

**pi-gate** is a lightweight DNS sinkhole designed to block unwanted URLs, such as advertisements, malware sites, and trackers. It operates as a DNS server, filtering traffic at the network level to enhance privacy and security. Built for efficiency, it is optimized for low-resource devices like the Raspberry Pi Zero.

---

## Features

### ✅ Current Features
- **DNS Sinkhole Functionality**: Blocks unwanted domains by intercepting DNS queries.
- **Lightweight & Fast**: Designed to run efficiently on minimal hardware.
- **Centralized Configuration**: Environment-based configuration with sensible defaults.
- **Enhanced Logging System**: Consistent logging across all components with configurable levels.
- **Configurable Blocklists**: Supports loading custom blocklists for domain filtering.
- **Command-Line Interface (CLI)**: `pi-gate start`, `stop`, `status`, and `update-blocklist` commands.
- **Background Execution**: Runs as a background service using Poetry.
- **Modern Dashboard**: Real-time statistics, filtering, and sorting of DNS queries.
- **Cross-Platform Support**: Uses tempfile and home directory fallbacks for better portability.

### 🚀 Upcoming Features
- **Optimized AsyncIO Handling**: Improve efficiency in DNS request processing.
- **Dashboard Enhancements**:
  - View DNS logs in real-time.
  - Whitelist management: Allow specific domains.
  - IP Management: Block/allow specific IPs if required.
- **Multiprocessing Support**: Enhance performance for handling multiple requests simultaneously.
- **Better Deployment Support**: Simplified installation and setup.

---

## How It Works

A DNS sinkhole intercepts DNS queries and returns a null response (or a specific IP) for blocked domains. Instead of reaching the actual malicious or ad-serving server, the request is stopped at the DNS level, preventing unwanted content from loading.

## DNS Sinkhole Diagram



### 📌 DNS Sinkhole Workflow
1. Device requests a domain (e.g., `example.com`).
2. `pi-gate` checks its blocklist.
   - If blocked, returns a null IP (`0.0.0.0` or `127.0.0.1`).
   - If allowed, forwards the request to the upstream DNS (e.g., Google DNS, Cloudflare).
3. The response is logged and returned to the client.
4. Blocked domains do not load, improving security and privacy.

---

## Installation & Usage

### 📥 Prerequisites
- Python 3.11+
- Poetry (for dependency management)

### 🔧 Installation
```bash
# Clone the repository
git clone https://github.com/workdone0/pi-gate.git
cd pi-gate

# Install dependencies
poetry install
```

### ⚙️ Configuration (Optional)
pi-gate can be configured using environment variables. Copy the example config and modify as needed:

```bash
# Copy the example configuration
cp config.example.env .env

# Edit the configuration
nano .env
```

Available configuration options:
- `PI_GATE_DNS_HOST`: DNS server listen address (default: 0.0.0.0)
- `PI_GATE_DNS_PORT`: DNS server port (default: 53)
- `PI_GATE_DASHBOARD_HOST`: Dashboard listen address (default: 0.0.0.0)
- `PI_GATE_DASHBOARD_PORT`: Dashboard port (default: 8050)
- `PI_GATE_UPSTREAM_DNS`: Upstream DNS server (default: 8.8.8.8:53)
- `PI_GATE_BLOCKLIST_URL`: Blocklist URL (default: hagezi/pro.txt)
- `PI_GATE_LOG_LEVEL`: Logging level (default: INFO)

### ▶️ Running pi-gate
```bash
# Start the DNS sinkhole
poetry run pi-gate start

# Stop the service
poetry run pi-gate stop

# Check status
poetry run pi-gate status

# Update blocklist
poetry run pi-gate update-blocklist

# Update blocklist from custom URL
poetry run pi-gate update-blocklist --url https://example.com/blocklist.txt
```

### 📊 Dashboard
Access the dashboard at `http://localhost:8050` to view:
- Real-time DNS query statistics
- Recent DNS queries with filtering and sorting
- Blocked vs allowed query counts
- Success rate metrics

---

## Contributing
Contributions are welcome! Feel free to open issues or submit pull requests to enhance `pi-gate`.

---

## License
[MIT License](LICENSE)



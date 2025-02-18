#!/usr/bin/env python3
import asyncio
import aiohttp
import logging
from dnslib import DNSRecord, DNSHeader, RR, A, QTYPE

# -------------------------------
# Configuration Section
# -------------------------------

# Pre-existing blocklist URLs for ads.
BLOCKLIST_URLS = [
    "https://raw.githubusercontent.com/AdAway/adaway.github.io/master/hosts.txt",
    "http://sbc.io/hosts/hosts"
]

# The sinkhole IP to return for blocked domains.
SINKHOLE_IP = "0.0.0.0"

# Upstream DNS server (for non-blocked queries)
UPSTREAM_DNS = ("8.8.8.8", 53)

# Listen address and port
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 53

# Global variable to hold the blocked domains
BLOCKED_DOMAINS = set()

# -------------------------------
# Logging Configuration
# -------------------------------
LOG_FILE = "/tmp/dns_sinkhole.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# -------------------------------
# Blocklist Loading Functions
# -------------------------------

async def load_blocklist(url):
    blocked = set()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    for line in text.splitlines():
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split()
                        if len(parts) >= 2:
                            domain = parts[1].lower()
                            if domain not in ("localhost", "local"):
                                blocked.add(domain)
                else:
                    logging.warning(f"Failed to download blocklist from {url} (HTTP {resp.status})")
    except Exception as e:
        logging.error(f"Error loading blocklist from {url}: {e}")
    return blocked

async def load_all_blocklists():
    global BLOCKED_DOMAINS
    tasks = [load_blocklist(url) for url in BLOCKLIST_URLS]
    results = await asyncio.gather(*tasks)
    for result in results:
        BLOCKED_DOMAINS.update(result)
    logging.info(f"Loaded {len(BLOCKED_DOMAINS)} blocked domains.")

# -------------------------------
# Helper Functions
# -------------------------------

def is_blocked(query_name):
    qn = str(query_name).rstrip('.').lower()
    for blocked in BLOCKED_DOMAINS:
        if qn == blocked or qn.endswith("." + blocked):
            return True
    return False

# -------------------------------
# Asynchronous Upstream Query
# -------------------------------

class DnsClientProtocol(asyncio.DatagramProtocol):
    def __init__(self, request_data, loop):
        self.request_data = request_data
        self.loop = loop
        self.on_response = loop.create_future()

    def connection_made(self, transport):
        self.transport = transport
        self.transport.sendto(self.request_data)

    def datagram_received(self, data, addr):
        if not self.on_response.done():
            self.on_response.set_result(data)

    def error_received(self, exc):
        if not self.on_response.done():
            self.on_response.set_exception(exc)

    def connection_lost(self, exc):
        if not self.on_response.done():
            self.on_response.set_exception(exc or Exception("Connection lost"))

async def forward_query(data):
    loop = asyncio.get_running_loop()
    try:
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: DnsClientProtocol(data, loop),
            remote_addr=UPSTREAM_DNS
        )
        try:
            response = await asyncio.wait_for(protocol.on_response, timeout=2)
            return response
        except asyncio.TimeoutError:
            logging.warning("Timeout while forwarding query to upstream DNS.")
            return None
        finally:
            transport.close()
    except Exception as e:
        logging.error(f"Error forwarding query: {e}")
        return None

# -------------------------------
# Asyncio DNS Server Protocol
# -------------------------------

class DnsServerProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport
        logging.info(f"DNS server listening on {LISTEN_HOST}:{LISTEN_PORT}")

    def datagram_received(self, data, addr):
        asyncio.create_task(self.handle_query(data, addr))

    async def handle_query(self, data, addr):
        try:
            request = DNSRecord.parse(data)
            qname = request.q.qname
            qtype = QTYPE[request.q.qtype]
            client_ip = addr[0]
            logging.info(f"Received query from {client_ip} for {qname} (type {qtype})")

            if is_blocked(qname):
                reply = DNSRecord(
                    DNSHeader(id=request.header.id, qr=1, aa=1, ra=1),
                    q=request.q
                )
                reply.add_answer(
                    RR(rname=qname, rtype=QTYPE.A, rclass=1, ttl=60, rdata=A(SINKHOLE_IP))
                )
                response_data = reply.pack()
                logging.info(f"Blocked domain {qname}. Returning sinkhole IP {SINKHOLE_IP}.")
            else:
                response_data = await forward_query(data)
                if response_data is None:
                    reply = DNSRecord(
                        DNSHeader(id=request.header.id, qr=1, ra=1, rcode=2),
                        q=request.q
                    )
                    response_data = reply.pack()
                logging.info(f"Forwarded domain {qname} to upstream DNS.")

            self.transport.sendto(response_data, addr)
        except Exception as e:
            logging.error(f"Error handling DNS query: {e}")

# -------------------------------
# Main Entry Point
# -------------------------------

async def start_dns_server():
    await load_all_blocklists()
    loop = asyncio.get_running_loop()
    listen_addr = (LISTEN_HOST, LISTEN_PORT)
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: DnsServerProtocol(),
        local_addr=listen_addr
    )
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logging.info("Shutting down the DNS sinkhole server.")
    finally:
        transport.close()

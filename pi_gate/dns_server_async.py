#!/usr/bin/env python3
import asyncio
import aiohttp
from dnslib import DNSRecord, DNSHeader, RR, A, QTYPE

# -------------------------------
# Configuration Section
# -------------------------------

# Pre-existing blocklist URLs for ads.
# This example uses AdAway's hosts file. You can add more URLs if desired.
BLOCKLIST_URLS = [
    "https://raw.githubusercontent.com/AdAway/adaway.github.io/master/hosts.txt",
    "http://sbc.io/hosts/hosts"
]

# The sinkhole IP to return for blocked domains.
SINKHOLE_IP = "0.0.0.0"

# Upstream DNS server (for non-blocked queries)
UPSTREAM_DNS = ("8.8.8.8", 53)

# Listen address and port (port 53 usually requires root privileges;
# use an unprivileged port like 5353 for testing)
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 53

# Global variable to hold the blocked domains
BLOCKED_DOMAINS = set()

# -------------------------------
# Blocklist Loading Functions
# -------------------------------

async def load_blocklist(url):
    """
    Downloads a blocklist from a URL and returns a set of domains.
    Assumes the file is in a hosts-file format (e.g., "0.0.0.0 ads.example.com").
    """
    blocked = set()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    for line in text.splitlines():
                        line = line.strip()
                        # Skip empty lines and comments
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split()
                        if len(parts) >= 2:
                            # In hosts files the domain is usually the second token.
                            domain = parts[1].lower()
                            # Optionally ignore local entries:
                            if domain not in ("localhost", "local"):
                                blocked.add(domain)
                else:
                    print(f"Failed to download blocklist from {url} (HTTP {resp.status})")
    except Exception as e:
        print(f"Error loading blocklist from {url}: {e}")
    return blocked

async def load_all_blocklists():
    """Loads all blocklists from the given URLs and updates BLOCKED_DOMAINS."""
    global BLOCKED_DOMAINS
    tasks = [load_blocklist(url) for url in BLOCKLIST_URLS]
    results = await asyncio.gather(*tasks)
    for result in results:
        BLOCKED_DOMAINS.update(result)
    print(f"Loaded {len(BLOCKED_DOMAINS)} blocked domains.")

# -------------------------------
# Helper Functions
# -------------------------------

def is_blocked(query_name):
    """
    Check if the query name should be blocked.
    The check is case-insensitive and returns True if the query is an exact match
    or if it is a subdomain of any blocked domain.
    """
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
        # Send the DNS request as soon as the connection is made
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
    """
    Forwards the DNS query to an upstream DNS server asynchronously and returns the response.
    """
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
            print("Timeout while forwarding query to upstream DNS.")
            return None
        finally:
            transport.close()
    except Exception as e:
        print("Error forwarding query:", e)
        return None

# -------------------------------
# Asyncio DNS Server Protocol
# -------------------------------

class DnsServerProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport
        print(f"DNS server listening on {LISTEN_HOST}:{LISTEN_PORT}")

    def datagram_received(self, data, addr):
        # Handle each incoming DNS query in its own asyncio Task
        asyncio.create_task(self.handle_query(data, addr))

    async def handle_query(self, data, addr):
        try:
            request = DNSRecord.parse(data)
            qname = request.q.qname
            qtype = QTYPE[request.q.qtype]
            client_ip = addr[0]
            print(f"Received query from {client_ip} for {qname} (type {qtype})")

            if is_blocked(qname):
                # Build a DNS response with the sinkhole IP
                reply = DNSRecord(
                    DNSHeader(id=request.header.id, qr=1, aa=1, ra=1),
                    q=request.q
                )
                reply.add_answer(
                    RR(rname=qname, rtype=QTYPE.A, rclass=1, ttl=60, rdata=A(SINKHOLE_IP))
                )
                response_data = reply.pack()
                print(f"Blocked domain {qname}. Returning sinkhole IP {SINKHOLE_IP}.")
            else:
                # Forward the request to the upstream DNS server.
                response_data = await forward_query(data)
                if response_data is None:
                    # On failure, return a SERVFAIL response.
                    reply = DNSRecord(
                        DNSHeader(id=request.header.id, qr=1, ra=1, rcode=2),
                        q=request.q
                    )
                    response_data = reply.pack()
                print(f"Forwarded domain {qname} to upstream DNS.")

            self.transport.sendto(response_data, addr)
        except Exception as e:
            print("Error handling DNS query:", e)

# -------------------------------
# Main Entry Point
# -------------------------------

async def start_dns_server():
    # First, load all blocklists.
    await load_all_blocklists()

    loop = asyncio.get_running_loop()
    listen_addr = (LISTEN_HOST, LISTEN_PORT)
    # Create the UDP server endpoint.
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: DnsServerProtocol(),
        local_addr=listen_addr
    )

    try:
        # Keep the server running indefinitely.
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("\nShutting down the DNS sinkhole server.")
    finally:
        transport.close()
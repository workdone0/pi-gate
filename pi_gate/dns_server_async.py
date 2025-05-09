#!/usr/bin/env python3
import asyncio
import os
import time
from typing import Optional
import aiohttp
import uvloop
import logging
from dnslib import DNSRecord, DNSHeader, RR, A, QTYPE
from .database import log_query
from .blm_filter import initialize_bloom


blocklist_url = "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/hosts/pro.txt"

SINKHOLE_IP = "0.0.0.0"

UPSTREAM_DNS = ("8.8.8.8", 53)

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 53

# Global variable to hold the bloom filter
BLOOM = None
# -------------------------------
# Logging Configuration
# -------------------------------
LOG_FILE = "/tmp/dns_sinkhole.log"

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
            if BLOOM.check_url(str(qname)):
                reply = DNSRecord(
                    DNSHeader(id=request.header.id, qr=1, aa=1, ra=1),
                    q=request.q
                )
                reply.add_answer(
                    RR(rname=qname, rtype=QTYPE.A, rclass=1, ttl=60, rdata=A(SINKHOLE_IP))
                )
                response_data = reply.pack()
                await log_query(client_ip=client_ip, domain=str(qname), blocked=1, success=1)
            else:
                response_data = await forward_query(data)
                success=1
                if response_data is None:
                    success=0
                    reply = DNSRecord(
                        DNSHeader(id=request.header.id, qr=1, ra=1, rcode=2),
                        q=request.q
                    )
                    response_data = reply.pack()
                await log_query(client_ip=client_ip,domain=str(qname),blocked=0, success=success)

            self.transport.sendto(response_data, addr)
        except Exception as e:
            logging.error(f"Error handling DNS query: {e}")


async def setup_logging():
    try:
        # Make sure the directory exists for the log file
        log_dir = os.path.dirname(LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        # Close any existing handlers (important for daemonization)
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
            
        # Configure logging with file handler explicitly
        file_handler = logging.FileHandler(LOG_FILE)
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.addHandler(file_handler)
        
        logging.info("DNS Server starting in daemon mode")
    except Exception as e:
        # Write to a fallback location if there's an issue
        with open("/tmp/dns_server_error.log", "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error setting up logging: {str(e)}\n")


async def start_dns_server():
    await setup_logging()
    global BLOOM
    BLOOM = initialize_bloom(blocklist_url)
    uvloop.install()
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



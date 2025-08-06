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
from .config import config, setup_logging

# Global variable to hold the bloom filter
BLOOM = None
logger = setup_logging(config, "pi_gate.dns_server")

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
            remote_addr=config.upstream_dns
        )
        try:
            response = await asyncio.wait_for(protocol.on_response, timeout=config.dns_timeout)
            return response
        except asyncio.TimeoutError:
            logger.warning("Timeout while forwarding query to upstream DNS.")
            return None
        finally:
            transport.close()
    except Exception as e:
        logger.error(f"Error forwarding query: {e}")
        return None


# -------------------------------
# Asyncio DNS Server Protocol
# -------------------------------

class DnsServerProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport
        logger.info(f"DNS server listening on {config.dns_listen_host}:{config.dns_listen_port}")

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
                    RR(rname=qname, rtype=QTYPE.A, rclass=1, ttl=60, rdata=A(config.sinkhole_ip))
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
            logger.error(f"Error handling DNS query: {e}")


async def start_dns_server():
    global BLOOM
    logger.info("Initializing DNS server...")
    BLOOM = initialize_bloom()
    if BLOOM is None:
        logger.error("Failed to initialize bloom filter. Exiting.")
        return
    
    logger.info("DNS server initialized successfully")
    uvloop.install()
    loop = asyncio.get_running_loop()
    listen_addr = (config.dns_listen_host, config.dns_listen_port)
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: DnsServerProtocol(),
        local_addr=listen_addr
    )
    try:
        logger.info("DNS server running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down the DNS sinkhole server.")
    finally:
        transport.close()



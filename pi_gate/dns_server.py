import socketserver
from dnslib import DNSRecord
from .database import log_request

class DNSHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data, socket = self.request
        request = DNSRecord.parse(data)
        domain = str(request.q.qname)
        log_request(domain)
        print(f"Logged DNS request: {domain}")
        print(f"Received DNS request: {request.q.qname}")

        # Create a response (modify as needed)
        reply = request.reply()
        reply.add_answer(*request.q.qname, 1, 1, 300, "1.1.1.1")  # Example response

        socket.sendto(reply.pack(), self.client_address)


def start_dns_server(host="0.0.0.0", port=53):
    with socketserver.UDPServer((host, port), DNSHandler) as server:
        print(f"DNS Server running on {host}:{port}")
        server.serve_forever()

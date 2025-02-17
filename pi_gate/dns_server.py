import socketserver
from .database import log_request
from dnslib import DNSRecord, QTYPE

UPSTREAM_DNS = "8.8.8.8"
UPSTREAM_PORT = 53

class DNSHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data, socket = self.request
        request = DNSRecord.parse(data)
        query = request.q.qname
        qname = request.q.qname
        qtype = request.q.qtype
        print("------ Request (%s): %r (%s)" % (str(self.client_address),qname.label,QTYPE[qtype]))
        # log_request(query)

        # Forward the request to upstream DNS
        with socketserver.socket.socket(socketserver.socket.AF_INET, socketserver.socket.SOCK_DGRAM) as sock:
            sock.sendto(data, (UPSTREAM_DNS, UPSTREAM_PORT))
            response_data, _ = sock.recvfrom(512)

        socket.sendto(response_data, self.client_address)



def start_dns_server(host="0.0.0.0", port=53):
    with socketserver.UDPServer((host, port), DNSHandler) as server:
        print(f"DNS logger running on port {port}...")
        server.allow_reuse_address = True
        server.serve_forever()

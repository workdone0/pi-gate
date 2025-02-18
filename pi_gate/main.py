from multiprocessing import Process
import asyncio
import os
import signal
from .dashboard import start_dashboard
from .database import init_db
from .dns_server_async import start_dns_server

def start_dns():
    """Run the async DNS server"""
    asyncio.run(start_dns_server())

def start_services():
    """Start DNS server and dashboard in separate processes"""
    init_db()

    dns_process = Process(target=start_dns, daemon=False)
    dash_process = Process(target=start_dashboard, daemon=False)

    dns_process.start()
    dash_process.start()

    print(f"Started DNS server (PID: {dns_process.pid})")
    print(f"Started Dashboard (PID: {dash_process.pid})")

    return dns_process.pid, dash_process.pid

def stop_services():
    """Stop services by reading the PID file"""
    PID_FILE = "/tmp/pi_gate.pid"

    if not os.path.exists(PID_FILE):
        print("pi-gate is not running!")
        return

    with open(PID_FILE, "r") as f:
        pids = f.read().strip().split("\n")

    for pid in pids:
        try:
            os.kill(int(pid), signal.SIGTERM)
            print(f"Stopped process {pid}")
        except ProcessLookupError:
            print(f"Process {pid} not found, removing from PID file.")

    os.remove(PID_FILE)

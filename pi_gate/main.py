from multiprocessing import Process
import asyncio
import os
import signal
import sys
from .dashboard import start_dashboard
from .database import init_db
from .dns_server_async import start_dns_server

PID_FILE = "/tmp/pi_gate.pid"

def start_dns():
    """Run the async DNS server"""
    asyncio.run(start_dns_server())

def daemonize(func):
    """Daemonize a function using os.fork()"""
    pid = os.fork()
    if pid > 0:
        sys.exit(0)  # Exit parent process

    os.setsid()  # Create a new session, detach from terminal
    pid = os.fork()
    if pid > 0:
        sys.exit(0)  # Exit second parent

    func()  # Run the actual function

def start_services():
    """Start DNS server and dashboard in background"""
    init_db()

    dns_process = Process(target=daemonize, args=(start_dns,), daemon=False)
    dash_process = Process(target=daemonize, args=(start_dashboard,), daemon=False)

    dns_process.start()
    dash_process.start()

    with open(PID_FILE, "w") as f:
        f.write(f"{dns_process.pid}\n{dash_process.pid}\n")

    print(f"Started DNS server (PID: {dns_process.pid})")
    print(f"Started Dashboard (PID: {dash_process.pid})")

def stop_services():
    """Stop services by reading the PID file"""
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
            print(f"Process {pid} not found, ignoring.")

    os.remove(PID_FILE)

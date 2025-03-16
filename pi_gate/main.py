from multiprocessing import Process
import asyncio
import os
import signal
import sys
import fcntl
from .dashboard import start_dashboard
from .database import init_db
from .dns_server_async import start_dns_server

PID_FILE = "/tmp/pi_gate.pid"


def start_dns():
    """Run the async DNS server"""
    # Write PID to the main PID file using file locking to avoid race conditions
    with open(PID_FILE, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)  # Exclusive lock
        f.write(f"{os.getpid()}\n")
        fcntl.flock(f, fcntl.LOCK_UN)  # Release lock
    
    asyncio.run(start_dns_server())

def start_dash():
    """Run the dashboard"""
    # Write PID to the main PID file using file locking
    with open(PID_FILE, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)  # Exclusive lock
        f.write(f"{os.getpid()}\n")
        fcntl.flock(f, fcntl.LOCK_UN)  # Release lock
    
    start_dashboard()

def daemonize(func):
    """Daemonize a function using os.fork()"""
    pid = os.fork()
    if pid > 0:
        return  # Exit first parent
    
    os.setsid()  # Create a new session, detach from terminal
    
    pid = os.fork()
    if pid > 0:
        sys.exit(0)  # Exit second parent
    
    # We're now in the grandchild process
    func()  # Run the actual function

async def start_services():
    """Start DNS server and dashboard in background"""
    await init_db()
    
    # Clear the PID file first
    with open(PID_FILE, "w") as f:
        pass  # Create empty file
    
    # Start processes with daemonization
    dns_process = Process(target=daemonize, args=(start_dns,), daemon=False)
    dash_process = Process(target=daemonize, args=(start_dash,), daemon=False)
    
    dns_process.start()
    dash_process.start()
    
    # Wait for immediate process to exit
    dns_process.join()
    dash_process.join()
    
    print(f"Started DNS server and Dashboard as daemons")
    print(f"PIDs written to {PID_FILE}")

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

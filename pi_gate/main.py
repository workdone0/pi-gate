from multiprocessing import Process
import asyncio
import os
import signal
import sys
import fcntl
from .dashboard import start_dashboard
from .database import init_db
from .dns_server_async import start_dns_server
from .config import config, setup_logging

logger = setup_logging(config, "pi_gate.main")


def start_dns():
    """Run the async DNS server"""
    # Write PID to the main PID file using file locking to avoid race conditions
    with open(config.pid_file, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)  # Exclusive lock
        f.write(f"{os.getpid()}\n")
        fcntl.flock(f, fcntl.LOCK_UN)  # Release lock
    
    logger.info("Starting DNS server process")
    asyncio.run(start_dns_server())

def start_dash():
    """Run the dashboard"""
    # Write PID to the main PID file using file locking
    with open(config.pid_file, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)  # Exclusive lock
        f.write(f"{os.getpid()}\n")
        fcntl.flock(f, fcntl.LOCK_UN)  # Release lock
    
    logger.info("Starting dashboard process")
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
    try:
        await init_db()
        
        # Clear the PID file first
        with open(config.pid_file, "w") as f:
            pass  # Create empty file
        
        # Start processes with daemonization
        dns_process = Process(target=daemonize, args=(start_dns,), daemon=False)
        dash_process = Process(target=daemonize, args=(start_dash,), daemon=False)
        
        dns_process.start()
        dash_process.start()
        
        # Wait for immediate process to exit
        dns_process.join()
        dash_process.join()
        
        logger.info("Started DNS server and Dashboard as daemons")
        print(f"Started DNS server and Dashboard as daemons")
        print(f"PIDs written to {config.pid_file}")
    except Exception as e:
        logger.error(f"Failed to start services: {e}")
        raise

def stop_services():
    """Stop services by reading the PID file"""
    if not config.pid_file.exists():
        logger.warning("pi-gate is not running!")
        print("pi-gate is not running!")
        return

    try:
        with open(config.pid_file, "r") as f:
            pids = f.read().strip().split("\n")

        for pid in pids:
            if pid.strip():  # Skip empty lines
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    logger.info(f"Stopped process {pid}")
                    print(f"Stopped process {pid}")
                except ProcessLookupError:
                    logger.warning(f"Process {pid} not found, ignoring.")
                    print(f"Process {pid} not found, ignoring.")
                except ValueError:
                    logger.warning(f"Invalid PID in file: {pid}")
                    print(f"Invalid PID in file: {pid}")

        config.pid_file.unlink()
        logger.info("Successfully stopped all pi-gate services")
    except Exception as e:
        logger.error(f"Error stopping services: {e}")
        print(f"Error stopping services: {e}")

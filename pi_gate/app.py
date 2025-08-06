
import os
import typer
import asyncio
from .main import start_services, stop_services
from .config import config, setup_logging
from .blm_filter import initialize_bloom

app = typer.Typer()
logger = setup_logging(config, "pi_gate.app")

@app.command()
def start():
    """Start pi-gate services in the background"""
    if config.pid_file.exists():
        logger.error("pi-gate is already running!")
        print("pi-gate is already running!")
        raise typer.Exit(1)

    try:
        asyncio.run(start_services())
        logger.info("pi-gate started successfully")
        print("pi-gate started successfully.")
    except Exception as e:
        logger.error(f"Failed to start pi-gate: {e}")
        print(f"Failed to start pi-gate: {e}")
        raise typer.Exit(1)

@app.command()
def stop():
    """Stop the running pi-gate services"""
    try:
        stop_services()
        logger.info("pi-gate stopped successfully")
        print("pi-gate stopped.")
    except Exception as e:
        logger.error(f"Failed to stop pi-gate: {e}")
        print(f"Failed to stop pi-gate: {e}")
        raise typer.Exit(1)

@app.command()
def update_blocklist(
    url: str = typer.Option(None, "--url", "-u", help="URL of the blocklist to download"),
    force: bool = typer.Option(False, "--force", "-f", help="Force update even if bloom filter exists")
):
    """Update the blocklist from a URL"""
    try:
        blocklist_url = url or config.default_blocklist_url
        logger.info(f"Updating blocklist from: {blocklist_url}")
        print(f"Updating blocklist from: {blocklist_url}")
        
        # Initialize bloom filter with the new URL
        bloom = initialize_bloom(blocklist_url)
        if bloom is None:
            logger.error("Failed to update blocklist")
            print("Failed to update blocklist")
            raise typer.Exit(1)
        
        logger.info("Blocklist updated successfully")
        print("Blocklist updated successfully")
        
    except Exception as e:
        logger.error(f"Failed to update blocklist: {e}")
        print(f"Failed to update blocklist: {e}")
        raise typer.Exit(1)

@app.command()
def status():
    """Show the current status of pi-gate"""
    try:
        if config.pid_file.exists():
            with open(config.pid_file, "r") as f:
                pids = f.read().strip().split("\n")
            print(f"pi-gate is running with {len(pids)} processes")
            for i, pid in enumerate(pids, 1):
                print(f"  Process {i}: PID {pid}")
        else:
            print("pi-gate is not running")
        
        # Check if bloom filter exists
        if config.bloom_filter_file.exists():
            print(f"Bloom filter exists: {config.bloom_filter_file}")
        else:
            print("Bloom filter not found")
            
        # Check if database exists
        if config.database_file.exists():
            print(f"Database exists: {config.database_file}")
        else:
            print("Database not found")
            
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        print(f"Failed to get status: {e}")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()

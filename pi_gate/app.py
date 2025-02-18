import os
import typer
from .main import start_services, stop_services

app = typer.Typer()
PID_FILE = "/tmp/pi_gate.pid"

@app.command()
def start():
    """Start pi-gate services in the background"""
    if os.path.exists(PID_FILE):
        print("pi-gate is already running!")
        raise typer.Exit(1)

    dns_pid, dash_pid = start_services()

    with open(PID_FILE, "w") as f:
        f.write(f"{dns_pid}\n{dash_pid}")

    print("pi-gate started successfully.")

@app.command()
def stop():
    """Stop the running pi-gate services"""
    stop_services()
    print("pi-gate stopped.")

if __name__ == "__main__":
    app()

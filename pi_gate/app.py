import os
import typer
import subprocess
import signal
import pathlib

app = typer.Typer()
PID_FILE = "/tmp/pi_gate.pid"
LOG_FILE = "/tmp/pi_gate.log"

@app.command()
def start():
    """Start pi-gate services in the background"""
    if os.path.exists(PID_FILE):
        print("pi-gate is already running!")
        raise typer.Exit(1)

    try:
        # Get the absolute path to the pi_gate directory
        pi_gate_dir = pathlib.Path(__file__).parent.absolute()

        # Start DNS server
        dns_process = subprocess.Popen(
            ["python3", str(pi_gate_dir / "dns_server_async.py")],
            stdout=open(LOG_FILE, "a"),
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid  # Create new session
        )

        # Start dashboard
        dash_process = subprocess.Popen(
            ["python3", str(pi_gate_dir / "dashboard.py")],
            stdout=open(LOG_FILE, "a"),
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid # Create new session
        )

        with open(PID_FILE, "w") as f:
            f.write(f"{dns_process.pid}\n{dash_process.pid}\n")

        print(f"Started DNS server (PID: {dns_process.pid})")
        print(f"Started Dashboard (PID: {dash_process.pid})")

    except Exception as e:
        print(f"Error starting services: {e}")
        raise typer.Exit(1)

@app.command()
def stop():
    """Stop the running pi-gate services"""
    if not os.path.exists(PID_FILE):
        print("pi-gate is not running!")
        return

    try:
        with open(PID_FILE, "r") as f:
            pids = f.read().strip().split("\n")

        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGTERM)
                print(f"Stopped process {pid}")
            except ProcessLookupError:
                print(f"Process {pid} not found, ignoring.")

        os.remove(PID_FILE)

    except Exception as e:
        print(f"Error stopping services: {e}")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
# pi_gate/dashboard.py
import dash
from dash import dcc, html
import logging
from pi_gate.database import fetch_logs

LOG_FILE = "/tmp/pi_gate.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("DNS Logs Dashboard"),
    dcc.Interval(id="interval-component", interval=5000, n_intervals=0),  # Refresh every 5s
    html.Div(id="table-content")
])

@app.callback(
    dash.Output("table-content", "children"),
    [dash.Input("interval-component", "n_intervals")]
)
def update_table(n):
    try:
        logs = fetch_logs()
        return [html.P(f"{log}") for log in logs]
    except Exception as e:
        logging.error(f"Error updating table: {e}")
        return [html.P("Error loading logs.")]

def start_dashboard():
    logging.info("Starting dashboard...")
    app.run_server(debug=False, host="0.0.0.0", port=8050)
    logging.info("Dashboard stopped.")
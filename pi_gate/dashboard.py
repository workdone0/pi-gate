import dash
from dash import dcc, html
import sqlite3
import pandas as pd

app = dash.Dash(__name__)

def fetch_logs():
    conn = sqlite3.connect("dns_logs.db")
    df = pd.read_sql_query("SELECT * FROM dns_requests", conn)
    conn.close()
    return df.to_dict("records")

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
    logs = fetch_logs()
    return [html.P(f"{log}") for log in logs]

def start_dashboard():
    app.run_server(debug=True, host="0.0.0.0", port=8050)

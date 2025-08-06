import dash
from dash import dcc, html, dash_table
import logging
import asyncio
from datetime import datetime
from .database import fetch_logs
from .config import config, setup_logging

logger = setup_logging(config, "pi_gate.dashboard")

app = dash.Dash(__name__, title="pi-gate Dashboard")

# Custom CSS for better styling
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>pi-gate Dashboard</title>
        {%favicon%}
        {%css%}
        <style>
            .dash-table-container {
                margin: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .dash-spreadsheet-container {
                border: 1px solid #ddd;
                border-radius: 8px;
            }
            .dash-cell {
                padding: 8px 12px;
                border-bottom: 1px solid #eee;
            }
            .dash-header {
                background-color: #f8f9fa;
                font-weight: bold;
                border-bottom: 2px solid #dee2e6;
            }
            .status-blocked {
                background-color: #ffebee;
                color: #c62828;
                font-weight: bold;
            }
            .status-allowed {
                background-color: #e8f5e8;
                color: #2e7d32;
                font-weight: bold;
            }
            .stats-container {
                display: flex;
                justify-content: space-around;
                margin: 20px;
                padding: 20px;
                background-color: #f8f9fa;
                border-radius: 8px;
            }
            .stat-box {
                text-align: center;
                padding: 15px;
                background-color: white;
                border-radius: 6px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            .stat-number {
                font-size: 24px;
                font-weight: bold;
                color: #1976d2;
            }
            .stat-label {
                font-size: 14px;
                color: #666;
                margin-top: 5px;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

app.layout = html.Div([
    html.Div([
        html.H1("pi-gate DNS Sinkhole Dashboard", 
                style={'textAlign': 'center', 'color': '#1976d2', 'marginBottom': '30px'}),
        
        # Statistics section
        html.Div([
            html.Div([
                html.Div(id="total-queries", className="stat-number"),
                html.Div("Total Queries", className="stat-label")
            ], className="stat-box"),
            html.Div([
                html.Div(id="blocked-queries", className="stat-number"),
                html.Div("Blocked Queries", className="stat-label")
            ], className="stat-box"),
            html.Div([
                html.Div(id="allowed-queries", className="stat-number"),
                html.Div("Allowed Queries", className="stat-label")
            ], className="stat-box"),
            html.Div([
                html.Div(id="success-rate", className="stat-number"),
                html.Div("Success Rate", className="stat-label")
            ], className="stat-box"),
        ], className="stats-container"),
        
        # Controls
        html.Div([
            html.Label("Refresh Interval (seconds):"),
            dcc.Slider(
                id="refresh-slider",
                min=1,
                max=30,
                step=1,
                value=config.dashboard_refresh_interval // 1000,
                marks={i: str(i) for i in range(1, 31, 5)},
                tooltip={"placement": "bottom", "always_visible": True}
            ),
        ], style={'margin': '20px', 'padding': '20px', 'backgroundColor': 'white', 'borderRadius': '8px'}),
        
        # Logs table
        html.Div([
            html.H3("Recent DNS Queries", style={'marginBottom': '15px'}),
            dash_table.DataTable(
                id="logs-table",
                columns=[
                    {"name": "Time", "id": "timestamp"},
                    {"name": "Client IP", "id": "client_ip"},
                    {"name": "Domain", "id": "domain"},
                    {"name": "Status", "id": "status"},
                    {"name": "Success", "id": "success"}
                ],
                style_cell={
                    'textAlign': 'left',
                    'padding': '8px',
                    'fontSize': '14px'
                },
                style_header={
                    'backgroundColor': '#f8f9fa',
                    'fontWeight': 'bold',
                    'border': '1px solid #dee2e6'
                },
                style_data_conditional=[
                    {
                        'if': {'column_id': 'status', 'filter_query': '{status} = "BLOCKED"'},
                        'backgroundColor': '#ffebee',
                        'color': '#c62828',
                        'fontWeight': 'bold'
                    },
                    {
                        'if': {'column_id': 'status', 'filter_query': '{status} = "ALLOWED"'},
                        'backgroundColor': '#e8f5e8',
                        'color': '#2e7d32',
                        'fontWeight': 'bold'
                    }
                ],
                page_size=50,
                sort_action="native",
                filter_action="native",
                style_table={'overflowX': 'auto'}
            )
        ], style={'margin': '20px'}),
        
        # Refresh interval
        dcc.Interval(
            id="interval-component", 
            interval=config.dashboard_refresh_interval, 
            n_intervals=0
        ),
    ])
])

@app.callback(
    [dash.Output("logs-table", "data"),
     dash.Output("total-queries", "children"),
     dash.Output("blocked-queries", "children"),
     dash.Output("allowed-queries", "children"),
     dash.Output("success-rate", "children")],
    [dash.Input("interval-component", "n_intervals"),
     dash.Input("refresh-slider", "value")]
)
def update_dashboard(n, refresh_interval):
    try:
        # Update interval if changed
        if refresh_interval:
            dcc.Interval.interval = refresh_interval * 1000
        
        logs = asyncio.run(fetch_logs(limit=config.dashboard_max_logs))
        
        # Process logs for display
        processed_logs = []
        total_queries = len(logs)
        blocked_count = 0
        allowed_count = 0
        success_count = 0
        
        for log in logs:
            # Format timestamp
            timestamp = log.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    formatted_time = str(timestamp)
            else:
                formatted_time = 'Unknown'
            
            # Determine status
            blocked = log.get('blocked', 0)
            success = log.get('success', 0)
            
            if blocked:
                status = "BLOCKED"
                blocked_count += 1
            else:
                status = "ALLOWED"
                allowed_count += 1
            
            if success:
                success_count += 1
            
            processed_logs.append({
                'timestamp': formatted_time,
                'client_ip': log.get('client_ip', 'Unknown'),
                'domain': log.get('domain', 'Unknown'),
                'status': status,
                'success': 'Yes' if success else 'No'
            })
        
        # Calculate success rate
        success_rate = f"{(success_count/total_queries*100):.1f}%" if total_queries > 0 else "0%"
        
        return processed_logs, total_queries, blocked_count, allowed_count, success_rate
        
    except Exception as e:
        logger.error(f"Error updating dashboard: {e}")
        return [], 0, 0, 0, "0%"

def start_dashboard():
    logger.info(f"Starting dashboard on {config.dashboard_host}:{config.dashboard_port}")
    app.run_server(
        debug=False, 
        host=config.dashboard_host, 
        port=config.dashboard_port
    )
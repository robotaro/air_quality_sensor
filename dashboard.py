#!/usr/bin/env python3
"""
Air Quality Real-time Visualizer with Buzzer Control
Uses Plotly Dash to create an interactive dashboard
"""

import json
import time
from datetime import datetime, timedelta, timezone
from collections import deque
from threading import Thread, Lock
import paho.mqtt.client as mqtt
import dash
from dash import dcc, html, Input, Output, State, callback
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd

# Try to import dateutil for better date parsing
try:
    from dateutil import parser as date_parser

    USE_DATEUTIL = True
except ImportError:
    USE_DATEUTIL = False

# Configuration
MQTT_BROKER = "192.168.1.114"
MQTT_PORT = 1883
MQTT_USER = ""
MQTT_PASSWORD = ""
MQTT_TOPIC_DATA = "airquality/sensor/data"
MQTT_TOPIC_COMMAND = "airquality/sensor/command"

# Visualization settings
WINDOW_MINUTES = 30  # Show last 30 minutes of data
UPDATE_INTERVAL = 1000  # Update every 1 second (milliseconds)
MAX_POINTS = 18000  # 30 min * 60 sec * 10 Hz = 18000 points


class DataStore:
    """Thread-safe data storage for real-time updates"""

    def __init__(self):
        self.data = deque(maxlen=MAX_POINTS)
        self.lock = Lock()
        self.last_update = time.time()

    def add_data(self, payload):
        with self.lock:
            # Convert timestamp to datetime
            timestamp_str = payload.get('timestamp')

            if timestamp_str:
                try:
                    if USE_DATEUTIL:
                        # Use dateutil for more flexible parsing
                        dt = date_parser.parse(timestamp_str)
                        # Convert to local time and make naive for simpler comparisons
                        if dt.tzinfo is not None:
                            dt = dt.astimezone().replace(tzinfo=None)
                        payload['datetime'] = dt
                    else:
                        # Handle ISO 8601 format manually
                        # First, try to parse as-is
                        try:
                            # Remove 'Z' suffix if present
                            if timestamp_str.endswith('Z'):
                                # Handle milliseconds if present
                                if '.' in timestamp_str:
                                    # Parse with milliseconds
                                    basic_timestamp = timestamp_str[:-1]
                                    dt = datetime.strptime(basic_timestamp, '%Y-%m-%dT%H:%M:%S.%f')
                                else:
                                    # Parse without milliseconds
                                    basic_timestamp = timestamp_str[:-1]
                                    dt = datetime.strptime(basic_timestamp, '%Y-%m-%dT%H:%M:%S')
                                # Convert from UTC to local time
                                utc_dt = dt.replace(tzinfo=timezone.utc)
                                local_dt = utc_dt.astimezone()
                                # Make naive
                                payload['datetime'] = local_dt.replace(tzinfo=None)
                            else:
                                # Try to parse with fromisoformat (Python 3.7+)
                                dt = datetime.fromisoformat(timestamp_str)
                                if dt.tzinfo is not None:
                                    dt = dt.astimezone().replace(tzinfo=None)
                                payload['datetime'] = dt
                        except:
                            # Final fallback
                            basic_timestamp = timestamp_str.replace('Z', '').replace('+00:00', '').split('.')[0]
                            payload['datetime'] = datetime.strptime(basic_timestamp, '%Y-%m-%dT%H:%M:%S')

                except (ValueError, TypeError) as e:
                    print(f"Error parsing timestamp '{timestamp_str}': {e}")
                    payload['datetime'] = datetime.now()
            else:
                # Use current time if no timestamp
                payload['datetime'] = datetime.now()

            self.data.append(payload)
            self.last_update = time.time()

    def get_dataframe(self):
        with self.lock:
            if not self.data:
                return pd.DataFrame()

            df = pd.DataFrame(list(self.data))

            # Ensure datetime column exists
            if 'datetime' not in df.columns:
                # Try to parse timestamp column if it exists
                if 'timestamp' in df.columns:
                    df['datetime'] = pd.to_datetime(df['timestamp'])
                else:
                    df['datetime'] = pd.to_datetime('now')

            # Sort by datetime
            df = df.sort_values('datetime')

            # Filter to window - use naive datetime for comparison
            cutoff_time = datetime.now() - timedelta(minutes=WINDOW_MINUTES)

            df = df[df['datetime'] >= cutoff_time]

            return df


# Global data store
data_store = DataStore()

# MQTT Setup
mqtt_client = mqtt.Client()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to MQTT broker")
        client.subscribe(MQTT_TOPIC_DATA)
        print(f"Subscribed to topic: {MQTT_TOPIC_DATA}")
    else:
        print(f"Failed to connect, return code {rc}")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())

        # Only process data messages (not status or response messages)
        if msg.topic == MQTT_TOPIC_DATA:
            print(
                f"Received data from: {payload.get('device_id', 'unknown')}, timestamp: {payload.get('timestamp', 'none')}")
            data_store.add_data(payload)
        else:
            print(f"Received message on topic {msg.topic}")
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Raw message: {msg.payload}")
    except Exception as e:
        print(f"Error processing message: {e}")
        print(f"Topic: {msg.topic}")
        print(f"Payload: {msg.payload}")


def on_disconnect(client, userdata, rc):
    print(f"Disconnected with result code {rc}")


def on_log(client, userdata, level, buf):
    print(f"MQTT Log: {buf}")


mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

if MQTT_USER:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)


# Start MQTT in background thread
def mqtt_thread():
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_forever()
    except Exception as e:
        print(f"MQTT error: {e}")


Thread(target=mqtt_thread, daemon=True).start()

# Initialize Dash app
app = dash.Dash(__name__)

# Define the layout
app.layout = html.Div([
    html.Div([
        html.H1("Air Quality Monitor Dashboard", style={'textAlign': 'center'}),
        html.Div(id='last-update', style={'textAlign': 'center', 'fontSize': '14px', 'color': '#666'}),
    ]),

    # Summary cards
    html.Div([
        html.Div([
            html.Div([
                html.H3("PM2.5", style={'marginBottom': '5px'}),
                html.H2(id='pm25-current', children='--'),
                html.P("μg/m³", style={'marginTop': '5px'})
            ], className='summary-card'),

            html.Div([
                html.H3("PM10", style={'marginBottom': '5px'}),
                html.H2(id='pm10-current', children='--'),
                html.P("μg/m³", style={'marginTop': '5px'})
            ], className='summary-card'),

            html.Div([
                html.H3("PM1.0", style={'marginBottom': '5px'}),
                html.H2(id='pm1-current', children='--'),
                html.P("μg/m³", style={'marginTop': '5px'})
            ], className='summary-card'),

            html.Div([
                html.H3("Data Points", style={'marginBottom': '5px'}),
                html.H2(id='data-count', children='0'),
                html.P("in buffer", style={'marginTop': '5px'})
            ], className='summary-card'),
        ], style={'display': 'flex', 'justifyContent': 'space-around', 'marginBottom': '30px'}),
    ]),

    # Buzzer Control Card
    html.Div([
        html.Div([
            html.H3("Buzzer Control", style={'marginBottom': '15px', 'color': '#2c3e50'}),
            html.Div([
                html.Div([
                    html.Label("Duty Cycle (0.0 - 1.0):", style={'marginBottom': '5px', 'display': 'block'}),
                    dcc.Input(
                        id='duty-cycle-input',
                        type='number',
                        value=0.0,
                        min=0.0,
                        max=1.0,
                        step=0.1,
                        style={'width': '100%', 'padding': '8px', 'borderRadius': '4px', 'border': '1px solid #ddd'}
                    ),
                ], style={'marginBottom': '15px'}),

                html.Div([
                    html.Label("Period (seconds):", style={'marginBottom': '5px', 'display': 'block'}),
                    dcc.Input(
                        id='period-input',
                        type='number',
                        value=1.0,
                        min=0.01,
                        step=0.1,
                        style={'width': '100%', 'padding': '8px', 'borderRadius': '4px', 'border': '1px solid #ddd'}
                    ),
                ], style={'marginBottom': '15px'}),

                html.Button(
                    'Send Command',
                    id='send-buzzer-command',
                    style={
                        'width': '100%',
                        'padding': '10px',
                        'backgroundColor': '#3498db',
                        'color': 'white',
                        'border': 'none',
                        'borderRadius': '4px',
                        'cursor': 'pointer',
                        'fontSize': '16px'
                    }
                ),

                html.Div(id='buzzer-status', style={'marginTop': '10px', 'textAlign': 'center', 'fontSize': '14px'}),
            ]),
        ], className='control-card', style={
            'background': 'white',
            'borderRadius': '8px',
            'padding': '20px',
            'boxShadow': '0 2px 4px rgba(0,0,0,0.1)',
            'maxWidth': '300px',
            'margin': '0 auto 30px'
        }),
    ]),

    # PM Concentration Chart
    dcc.Graph(id='pm-chart', style={'height': '400px'}),

    # Particle Count Chart
    dcc.Graph(id='particle-chart', style={'height': '400px'}),

    # Auto-refresh interval
    dcc.Interval(
        id='interval-component',
        interval=UPDATE_INTERVAL,
        n_intervals=0
    )
], style={'padding': '20px', 'fontFamily': 'Arial, sans-serif'})

# Add CSS styling
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body {
                margin: 0;
                background-color: #f5f5f5;
            }
            .summary-card {
                background: white;
                border-radius: 8px;
                padding: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                text-align: center;
                flex: 1;
                margin: 0 10px;
            }
            .summary-card h2 {
                margin: 10px 0;
                color: #2c3e50;
                font-size: 36px;
            }
            .summary-card h3 {
                margin: 0;
                color: #7f8c8d;
                font-size: 18px;
            }
            .summary-card p {
                margin: 0;
                color: #95a5a6;
                font-size: 14px;
            }
            button:hover {
                opacity: 0.9;
            }
            button:active {
                transform: translateY(1px);
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


@app.callback(
    Output('buzzer-status', 'children'),
    Input('send-buzzer-command', 'n_clicks'),
    State('duty-cycle-input', 'value'),
    State('period-input', 'value'),
    prevent_initial_call=True
)
def send_buzzer_command(n_clicks, duty_cycle, period):
    if n_clicks is None:
        return ""

    try:
        # Validate inputs
        if duty_cycle is None or period is None:
            return html.Div("Please enter valid values", style={'color': '#e74c3c'})

        # Constrain values
        duty_cycle = max(0.0, min(1.0, float(duty_cycle)))
        period = max(0.01, float(period))

        # Create MQTT message
        message = {
            "type": "buzzer",
            "duty_cycle": duty_cycle,
            "period": period,
            "id": f"dash_{int(time.time() * 1000)}"
        }

        # Publish to MQTT
        result = mqtt_client.publish(MQTT_TOPIC_COMMAND, json.dumps(message))

        if result.rc == 0:
            return html.Div(
                f"✓ Sent: {duty_cycle:.1f} duty, {period:.1f}s period",
                style={'color': '#2ecc71'}
            )
        else:
            return html.Div(
                f"Failed to send command (RC: {result.rc})",
                style={'color': '#e74c3c'}
            )

    except Exception as e:
        return html.Div(f"Error: {str(e)}", style={'color': '#e74c3c'})


@app.callback(
    [Output('pm-chart', 'figure'),
     Output('particle-chart', 'figure'),
     Output('pm25-current', 'children'),
     Output('pm10-current', 'children'),
     Output('pm1-current', 'children'),
     Output('data-count', 'children'),
     Output('last-update', 'children')],
    Input('interval-component', 'n_intervals')
)
def update_dashboard(n):
    df = data_store.get_dataframe()

    if df.empty:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            title="Waiting for data...",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=350
        )
        return empty_fig, empty_fig, '--', '--', '--', '0', 'No data yet'

    # PM Concentration Chart
    pm_fig = go.Figure()

    pm_fig.add_trace(go.Scatter(
        x=df['datetime'],
        y=df['pm1_0_atm'],
        mode='lines',
        name='PM1.0',
        line=dict(width=2, color='#3498db')
    ))

    pm_fig.add_trace(go.Scatter(
        x=df['datetime'],
        y=df['pm2_5_atm'],
        mode='lines',
        name='PM2.5',
        line=dict(width=2, color='#e74c3c')
    ))

    pm_fig.add_trace(go.Scatter(
        x=df['datetime'],
        y=df['pm10_atm'],
        mode='lines',
        name='PM10',
        line=dict(width=2, color='#2ecc71')
    ))

    pm_fig.update_layout(
        title='PM Concentrations (Atmospheric)',
        xaxis_title='Time',
        yaxis_title='Concentration (μg/m³)',
        hovermode='x unified',
        height=350,
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    # Particle Count Chart
    particle_fig = go.Figure()

    # Select specific particle sizes to display
    particle_sizes = [
        ('particles_03', '>0.3μm', '#9b59b6'),
        ('particles_05', '>0.5μm', '#3498db'),
        ('particles_10', '>1.0μm', '#2ecc71'),
        ('particles_25', '>2.5μm', '#e74c3c'),
        ('particles_50', '>5.0μm', '#f39c12'),
    ]

    for col, label, color in particle_sizes:
        if col in df.columns:
            particle_fig.add_trace(go.Scatter(
                x=df['datetime'],
                y=df[col],
                mode='lines',
                name=label,
                line=dict(width=2, color=color)
            ))

    particle_fig.update_layout(
        title='Particle Counts (per 0.1L air)',
        xaxis_title='Time',
        yaxis_title='Particle Count',
        hovermode='x unified',
        height=350,
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    # Get current values (latest)
    latest = df.iloc[-1]
    pm25_current = f"{latest['pm2_5_atm']:.1f}"
    pm10_current = f"{latest['pm10_atm']:.1f}"
    pm1_current = f"{latest['pm1_0_atm']:.1f}"

    # Data count
    data_count = f"{len(df):,}"

    # Last update time - convert to local time for display
    if latest['datetime'].tzinfo is not None:
        # Convert UTC to local time for display
        local_dt = latest['datetime'].astimezone()
        last_update = f"Last update: {local_dt.strftime('%H:%M:%S')}"
    else:
        last_update = f"Last update: {latest['datetime'].strftime('%H:%M:%S')}"

    return pm_fig, particle_fig, pm25_current, pm10_current, pm1_current, data_count, last_update


if __name__ == '__main__':
    print("Starting Air Quality Visualizer...")
    if USE_DATEUTIL:
        print("Using python-dateutil for timestamp parsing")
    else:
        print("python-dateutil not found, using fallback parser")
        print("For better compatibility, install: pip install python-dateutil")
    print(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
    print(f"Subscribing to topic: {MQTT_TOPIC_DATA}")
    print("Dashboard available at: http://localhost:8050")
    app.run_server(debug=False, host='127.0.0.1', port=8050)
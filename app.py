import dash
from dash import dcc, html, callback, Input, Output
import plotly.graph_objects as go
import pandas as pd
from pathlib import Path

try:
    import vnstock
except ImportError:
    vnstock = None

# Khởi tạo app
app = dash.Dash(__name__)
app.title = "Market Data Dashboard 2026"

# CSS
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
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
        }
        .navbar {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }
        .navbar h1 {
            margin: 0;
            font-size: 2em;
        }
        .container {
            max-width: 1400px;
            margin: 20px auto;
            padding: 0 20px;
        }
        .controls {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .control-row {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 15px;
            margin-bottom: 15px;
        }
        .control-group {
            display: flex;
            flex-direction: column;
        }
        .control-group label {
            font-weight: 600;
            margin-bottom: 5px;
            color: #333;
        }
        .control-group input, .control-group select {
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }
        .chart-container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .chart-container h3 {
            margin-top: 0;
            color: #667eea;
        }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .info-card {
            background: white;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .info-card-label {
            font-size: 12px;
            color: #999;
            text-transform: uppercase;
            font-weight: 600;
        }
        .info-card-value {
            font-size: 24px;
            font-weight: bold;
            color: #333;
            margin-top: 5px;
        }
        .positive { color: #27ae60; }
        .negative { color: #e74c3c; }
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
        }
        button:hover {
            background: #764ba2;
        }
    </style>
</head>
<body>
    {%app_entry%}
    <footer></footer>
    {%config%}
    {%scripts%}
    {%renderer%}
</body>
</html>
'''

app.layout = html.Div([
    # Navbar
    html.Div([
        html.H1("📊 Market Data Dashboard 2026"),
        html.P("Phân tích dữ liệu OHLCV thị trường chứng khoán Việt Nam")
    ], className="navbar"),
    
    # Container chính
    html.Div([
        # Điều khiển
        html.Div([
            html.Div([
                html.Div([
                    html.Label("Mã chứng khoán"),
                    dcc.Input(
                        id="symbol-input",
                        type="text",
                        placeholder="VD: FPT VHM VCB",
                        value="FPT VHM VCB",
                        style={"width": "100%"}
                    )
                ], className="control-group"),
                html.Div([
                    html.Label("Ngày bắt đầu"),
                    dcc.Input(
                        id="start-date",
                        type="date",
                        value="2025-01-01"
                    )
                ], className="control-group"),
                html.Div([
                    html.Label("Ngày kết thúc"),
                    dcc.Input(
                        id="end-date",
                        type="date",
                        value="2026-10-02"
                    )
                ], className="control-group"),
            ], className="control-row"),
            html.Button("Tải dữ liệu", id="load-btn", n_clicks=0)
        ], className="controls"),
        
        # Thông tin tóm tắt
        html.Div(id="info-cards", className="info-grid"),
        
        # Biểu đồ giá
        html.Div([
            html.H3("📈 Biểu đồ giá OHLC"),
            dcc.Loading(
                id="loading-price",
                type="default",
                children=[
                    dcc.Graph(id="price-chart")
                ]
            )
        ], className="chart-container"),
        
        # Biểu đồ khối lượng
        html.Div([
            html.H3("📊 Khối lượng giao dịch"),
            dcc.Loading(
                id="loading-volume",
                type="default",
                children=[
                    dcc.Graph(id="volume-chart")
                ]
            )
        ], className="chart-container"),
        
        # Bảng dữ liệu
        html.Div([
            html.H3("📋 Dữ liệu OHLCV"),
            html.Div(id="data-table")
        ], className="chart-container"),
        
        # Store dữ liệu
        dcc.Store(id="data-store")
    ], className="container")
])


@callback(
    Output("data-store", "data"),
    Input("load-btn", "n_clicks"),
    [
        Input("symbol-input", "value"),
        Input("start-date", "value"),
        Input("end-date", "value")
    ],
    prevent_initial_call=False
)
def load_data(n_clicks, symbols_str, start_date, end_date):
    if not symbols_str:
        return None
    
    symbols = [s.strip().upper() for s in symbols_str.split()]
    
    if vnstock is None:
        return {"error": "vnstock chưa cài"}
    
    all_data = {}
    
    for symbol in symbols:
        try:
            df = vnstock.stock_historical(
                symbol,
                start_date=start_date,
                end_date=end_date,
                interval="1D"
            )
            
            if df is not None and not df.empty:
                df = df.copy()
                df.columns = [col.lower() for col in df.columns]
                
                if 'date' not in df.columns:
                    df = df.reset_index()
                
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                all_data[symbol] = df.to_dict('records')
        except:
            pass
    
    return all_data


@callback(
    [
        Output("price-chart", "figure"),
        Output("volume-chart", "figure"),
        Output("data-table", "children"),
        Output("info-cards", "children")
    ],
    Input("data-store", "data")
)
def update_charts(data):
    if not data:
        return {}, {}, html.P("Không có dữ liệu"), []
    
    if "error" in data:
        return {}, {}, html.P(data["error"]), []
    
    # Biểu đồ giá
    price_fig = go.Figure()
    
    for symbol, records in data.items():
        df = pd.DataFrame(records)
        if not df.empty:
            price_fig.add_trace(go.Scatter(
                x=df['date'],
                y=df['close'],
                name=symbol,
                mode='lines',
                line=dict(width=2)
            ))
    
    price_fig.update_layout(
        title="Giá đóng cửa",
        xaxis_title="Ngày",
        yaxis_title="Giá (VND)",
        hovermode='x unified',
        height=500
    )
    
    # Biểu đồ khối lượng
    volume_fig = go.Figure()
    
    for symbol, records in data.items():
        df = pd.DataFrame(records)
        if not df.empty:
            volume_fig.add_trace(go.Bar(
                x=df['date'],
                y=df['volume'],
                name=symbol
            ))
    
    volume_fig.update_layout(
        title="Khối lượng giao dịch",
        xaxis_title="Ngày",
        yaxis_title="Khối lượng",
        barmode='group',
        height=400
    )
    
    # Bảng dữ liệu (hiển thị mã đầu tiên)
    first_symbol = list(data.keys())[0]
    df = pd.DataFrame(data[first_symbol])
    
    table_rows = []
    for idx, row in df.head(20).iterrows():
        table_rows.append(
            html.Tr([
                html.Td(row.get('date', '')),
                html.Td(f"{row.get('open', 0):.2f}"),
                html.Td(f"{row.get('high', 0):.2f}"),
                html.Td(f"{row.get('low', 0):.2f}"),
                html.Td(f"{row.get('close', 0):.2f}"),
                html.Td(f"{row.get('volume', 0):.0f}")
            ])
        )
    
    table = html.Table([
        html.Thead(html.Tr([
            html.Th("Ngày"),
            html.Th("Open"),
            html.Th("High"),
            html.Th("Low"),
            html.Th("Close"),
            html.Th("Volume")
        ])),
        html.Tbody(table_rows)
    ], style={"width": "100%", "border-collapse": "collapse"})
    
    # Info cards
    info_cards = []
    for symbol, records in data.items():
        df = pd.DataFrame(records)
        if not df.empty:
            latest = df.iloc[-1]
            info_cards.append(
                html.Div([
                    html.Div(f"{symbol}", className="info-card-label"),
                    html.Div(f"{latest.get('close', 0):.2f} VND", className="info-card-value"),
                    html.Div(f"Vol: {latest.get('volume', 0):.0f}", style={"font-size": "12px", "color": "#999"})
                ], className="info-card")
            )
    
    return price_fig, volume_fig, table, info_cards


if __name__ == "__main__":
    print("\n🚀 Chạy dashboard tại http://localhost:8050")
    app.run_server(debug=True, port=8050)

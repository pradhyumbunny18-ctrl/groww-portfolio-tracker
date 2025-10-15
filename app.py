import dash
from dash import dcc, html
import pandas as pd
import plotly.express as px
import yfinance as yf
from datetime import datetime, time
from dash.dependencies import Input, Output
from collections import defaultdict  # For aggregating qty

app = dash.Dash(__name__)

# Load your P/L summary (optional)
try:
    grouped = pd.read_csv('portfolio_summary.csv')
except FileNotFoundError:
    grouped = pd.DataFrame({
        'Ticker': ['ADANIPOWER', 'HDFCBANK', 'INFY'],
        'Allocation %': [32.2, 25.0, 12.5],
        'Returns %': [5.0, 3.2, 4.5]
    })

# Load holdings from CSV for qty and avg price
def load_holdings():
    try:
        holdings_df = pd.read_csv('holdings.csv')
        print("CSV Columns:", holdings_df.columns.tolist())  # Debug
        print("First few rows:\n", holdings_df.head())  # Debug
        # Aggregate: Sum quantity per ticker (only 'Buy' types)
        agg_data = defaultdict(lambda: {'total_qty': 0, 'total_cost': 0})
        for _, row in holdings_df.iterrows():
            if row['type'] == 'Buy':  # Filter buys
                ticker = str(row['ticker'])
                qty = row['quantity']
                avg_price = row['avg_price']
                agg_data[ticker]['total_qty'] += qty
                agg_data[ticker]['total_cost'] += qty * avg_price
        tickers = []
        holdings = {}
        for ticker, data in agg_data.items():
            if data['total_qty'] > 0:
                total_qty = data['total_qty']
                avg_price = data['total_cost'] / total_qty if total_qty > 0 else 0
                tickers.append(ticker)
                holdings[ticker] = {'qty': total_qty, 'avg_price': avg_price}
        print("Loaded holdings:", holdings)  # Debug
        if not tickers:
            raise ValueError("No valid buys in CSV.")
        return tickers, holdings
    except FileNotFoundError:
        print("holdings.csv not found. Using sample data.")
    except Exception as e:
        print(f"CSV issue: {e}. Using sample data.")
    # Sample fallback
    tickers = ['ADANIPOWER.NS', 'HDFCBANK.NS', 'INFY.NS']
    holdings = {
        'ADANIPOWER.NS': {'qty': 50, 'avg_price': 250.0},
        'HDFCBANK.NS': {'qty': 20, 'avg_price': 1500.0},
        'INFY.NS': {'qty': 40, 'avg_price': 1800.0}
    }
    return tickers, holdings

tickers, holdings = load_holdings()

def is_market_open():
    """Check NSE hours (Mon-Fri, 9:15-15:30 IST)."""
    now = datetime.now()
    return now.weekday() < 5 and time(9, 15) <= now.time() <= time(15, 30)

def fetch_live_prices(tickers):
    """Fetch latest prices with robust error handling, prioritizing live data."""
    if not tickers:
        return {}
    prices = {}
    print(f"Attempting to fetch prices for tickers: {tickers}")
    try:
        # Try 1-day with 1-minute interval for live data
        data = yf.download(tickers, period='1d', interval='1m', auto_adjust=False, prepost=True)
        print(f"Raw data from yf.download (1m): {data}")
        if not data.empty:
            latest_close = data['Close'].iloc[-1]
            print(f"Latest close values (1m): {latest_close}")
            for ticker in tickers:
                if ticker in latest_close.index:
                    prices[ticker] = latest_close[ticker]
        if not prices:  # Fallback to 2d if 1m fails
            data = yf.download(tickers, period='2d', interval='1d', auto_adjust=False, prepost=True)
            print(f"Raw data from yf.download (2d): {data}")
            if not data.empty:
                latest_close = data['Close'].iloc[-1]
                print(f"Latest close values (2d): {latest_close}")
                for ticker in tickers:
                    if ticker in latest_close.index:
                        prices[ticker] = latest_close[ticker]
            else:
                raise Exception("No data from 2d fetch")
    except Exception as e:
        print(f"Fetch error for all tickers: {e}")
        for ticker in tickers:
            try:
                ticker_data = yf.download(ticker, period='1d', interval='1m', auto_adjust=False, prepost=True)
                print(f"Individual data for {ticker} (1m): {ticker_data}")
                if not ticker_data.empty:
                    prices[ticker] = ticker_data['Close'].iloc[-1]
                else:
                    ticker_data = yf.download(ticker, period='2d', interval='1d', auto_adjust=False, prepost=True)
                    print(f"Individual data for {ticker} (2d): {ticker_data}")
                    if not ticker_data.empty:
                        prices[ticker] = ticker_data['Close'].iloc[-1]
                    else:
                        prices[ticker] = holdings.get(ticker, {'avg_price': 0})['avg_price']
            except Exception as te:
                print(f"Fetch error for {ticker}: {te}")
                prices[ticker] = holdings.get(ticker, {'avg_price': 0})['avg_price']
    print(f"Fetched prices: {prices}")
    return prices
def build_holdings_df(tickers, holdings):
    """Build table data with live LTP, handling invalid prices."""
    prices = fetch_live_prices(tickers)
    df_data = []
    for ticker in tickers:
        if ticker in holdings:
            h = holdings[ticker]
            ltp = prices.get(ticker)
            if not isinstance(ltp, (int, float)) or pd.isna(ltp):
                ltp = h['avg_price']
            value = h['qty'] * ltp
            pct_chg = ((ltp - h['avg_price']) / h['avg_price']) * 100 if h['avg_price'] > 0 else 0
            unrealized = value - (h['qty'] * h['avg_price'])
            df_data.append([
                ticker.replace('.NS', ''),
                h['qty'],
                f"{h['avg_price']:.2f}",
                f"{ltp:.2f}",
                pct_chg,  # Store as float, not formatted string
                f"{value:.2f}",
                f"{unrealized:.2f}"
            ])
    df = pd.DataFrame(df_data, columns=['Ticker', 'Net Qty', 'Avg Price', 'LTP', '%Chg', 'Value', 'Unrealized'])
    df['%Chg'] = df['%Chg'].round(2)  # Ensure %Chg is numeric
    return df.sort_values('Value', ascending=False) if not df.empty else pd.DataFrame()

# Callback for auto-refresh: Updates every 30s
@app.callback(
    [
        Output('holdings-table', 'children'),
        Output('allocation-pie', 'figure'),
        Output('returns-bar', 'figure'),
        Output('trend-line', 'figure'),
        Output('timestamp', 'children'),
        Output('summary', 'children')
    ],
    [Input('interval-component', 'n_intervals')]
)
def update_dashboard(n):
    print(f"Callback triggered at {datetime.now().strftime('%H:%M:%S')} with n={n}")
    try:
        df = build_holdings_df(tickers, holdings)
        print(f"DataFrame: {df.head() if not df.empty else 'Empty'}")
        fig_pie_live = px.pie(df, values='Value', names='Ticker', title='Allocation %') if not df.empty else px.pie()
        fig_bar_live = px.bar(df, x='Ticker', y='%Chg', title='Returns % per Stock') if not df.empty else px.bar()
        try:
            multi_data = yf.download(tickers, period='1mo')['Close']
            print(f"Trend data: {multi_data.head() if not multi_data.empty else 'Empty'}")
            fig_trend_live = px.line(multi_data, title='1-Month Performance Trend') if not multi_data.empty else px.line(title='1-Month Performance Trend (Data unavailable)')
        except Exception as e:
            print(f"Trend fetch error: {e}")
            fig_trend_live = px.line(title='1-Month Performance Trend (Data unavailable)')
        if not df.empty:
            table_rows = [html.Tr([html.Td(str(col)) for col in row]) for row in df.itertuples(index=False, name=None)]
            table_header = html.Thead(html.Tr([html.Th(col) for col in df.columns]))
            table = html.Table([table_header, html.Tbody(table_rows)], style={'width': '100%', 'border': '1px solid black'})
        else:
            table = html.Div("No holdings data available. Check holdings.csv.")
        status = " (Live Market)" if is_market_open() else " (Market Closed - Last Close)"
        timestamp = html.Div(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{status} | Auto-refreshes every 30s", style={'textAlign': 'center', 'color': 'gray', 'marginTop': '20px'})
        total_return = df['%Chg'].mean() if not df.empty else 0
        total_value = pd.to_numeric(df['Value'], errors='coerce').sum() if not df.empty else 0
        summary = html.P(f"Total Return: {total_return:.2f}% | Total Value: ₹{total_value:.2f}", style={'textAlign': 'center', 'color': 'navy', 'fontSize': '18px', 'marginTop': '10px'})
        print("Returning data successfully")
        return table, fig_pie_live, fig_bar_live, fig_trend_live, timestamp, summary
    except Exception as e:
        print(f"Callback error: {e}")
        return html.Div("Error updating dashboard. Check terminal logs."), px.pie(), px.bar(), px.line(), html.Div(), html.P()
app.layout = html.Div([
    html.H1("My Groww Portfolio Tracker", style={'textAlign': 'center', 'color': 'navy'}),
    
    # Holdings Table (dynamic)
    html.Div(id='holdings-table', style={'width': '100%', 'marginBottom': '20px'}),
    
    # Allocation Pie (dynamic)
    dcc.Graph(id='allocation-pie'),
    
    # Returns Bar (dynamic)
    dcc.Graph(id='returns-bar'),
    
    # 1-Month Trend (dynamic)
    dcc.Graph(id='trend-line'),
    
    # Interval for 30s refresh
    dcc.Interval(id='interval-component', interval=30*1000, n_intervals=0),
    
    # Timestamp (dynamic)
    html.Div(id='timestamp'),
    
    # Summary (dynamic)
    html.Div(id='summary')
])

if __name__ == "__main__":
    app.run(debug=True)
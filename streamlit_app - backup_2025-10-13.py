import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from datetime import datetime, time
from collections import defaultdict

st.set_page_config(page_title="My Groww Portfolio Tracker", layout="wide")

st.title("My Groww Portfolio Tracker")

# Load holdings from CSV (aggregates buys)
def load_holdings():
    try:
        holdings_df = pd.read_csv('holdings.csv')
        agg_data = defaultdict(lambda: {'total_qty': 0, 'total_cost': 0})
        for _, row in holdings_df.iterrows():
            if row['type'] == 'Buy':
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
        return tickers, holdings
    except Exception as e:
        st.error(f"holdings.csv issue: {e}. Using sample data.")
        tickers = ['ADANIPOWER.NS']
        holdings = {'ADANIPOWER.NS': {'qty': 265, 'avg_price': 104.26}}
        return tickers, holdings

tickers, holdings = load_holdings()

def is_market_open():
    now = datetime.now()
    return now.weekday() < 5 and time(9, 15) <= now.time() <= time(15, 30)

def fetch_live_prices(tickers):
    try:
        if not is_market_open():
            data = yf.download(tickers, period='2d', interval='1d')['Close'].iloc[-1]
        else:
            data = yf.download(tickers, period='1d', interval='1m')['Close'].iloc[-1]
        return dict(zip(tickers, data))
    except Exception as e:
        st.error(f"Price fetch error: {e}")
        return {t: holdings[t]['avg_price'] for t in tickers if t in holdings}

def build_holdings_df(tickers, holdings):
    prices = fetch_live_prices(tickers)
    df_data = []
    numeric_data = []  # For safe calculations
    for ticker in tickers:
        if ticker in holdings:
            h = holdings[ticker]
            ltp = prices.get(ticker, h['avg_price'])
            invested = h['qty'] * h['avg_price']
            current_value = h['qty'] * ltp
            unrealized_pl = current_value - invested
            df_data.append({
                'Ticker': ticker.replace('.NS', ''),
                'Net Qty': h['qty'],
                'Avg Price': f"{h['avg_price']:.2f}",
                'Live Price': f"{ltp:.2f}",
                'Invested': f"{invested:.2f}",
                'Current Value': f"{current_value:.2f}",
                'Unrealized P/L': f"{unrealized_pl:.2f}"
            })
            numeric_data.append({
                'Invested': invested,
                'Current Value': current_value,
                'Unrealized P/L': unrealized_pl
            })
    df = pd.DataFrame(df_data)
    df_numeric = pd.DataFrame(numeric_data)
    return df.sort_values('Current Value', ascending=False), df_numeric

# Auto-refresh
if 'last_update' not in st.session_state:
    st.session_state.last_update = datetime.now()

st.sidebar.title("Controls")
if st.sidebar.button("Manual Refresh"):
    st.session_state.last_update = datetime.now()
    st.rerun()

if (datetime.now() - st.session_state.last_update).seconds >= 30:
    st.session_state.last_update = datetime.now()
    st.rerun()

# Live dashboard
df, df_numeric = build_holdings_df(tickers, holdings)

st.dataframe(df)

# Charts
fig_pie = px.pie(df, values='Current Value', names='Ticker', title='Allocation %')
st.plotly_chart(fig_pie)

fig_line = px.bar(df, x='Ticker', y='Unrealized P/L', title='Returns %')
st.plotly_chart(fig_line)

# Trend
multi_data = yf.download(tickers, period="1mo")['Close']
fig_trend = px.line(multi_data, title='1-Month Performance Trend')
st.plotly_chart(fig_trend)

# Metrics (fixed with numeric df)
status = " (Live Market)" if is_market_open() else " (Market Closed - Last Close)"
st.caption(f"Updated: {st.session_state.last_update.strftime('%Y-%m-%d %H:%M:%S')}{status} | Auto-refreshes every 30s")

total_return = (df_numeric['Unrealized P/L'].sum() / df_numeric['Invested'].sum()) * 100 if df_numeric['Invested'].sum() != 0 else 0
total_value = df_numeric['Current Value'].sum()

col1, col2 = st.columns(2)
with col1:
    st.metric("Total Return", f"{total_return:.2f}%")
with col2:
    st.metric("Total Value", f"₹{total_value:.2f}")
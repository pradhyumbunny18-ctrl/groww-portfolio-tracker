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
    prices = {}
    for ticker in tickers:
        try:
            # Individual fetch for reliability
            stock_data = yf.Ticker(ticker).history(period='1d', interval='1m' if is_market_open() else '1d', prepost=True)
            if not stock_data.empty:
                ltp = stock_data['Close'].iloc[-1]
                prices[ticker] = ltp
                print(f"Successfully fetched {ticker}: {ltp:.2f}")  # Debug log
            else:
                raise ValueError("Empty data")
        except Exception as e:
            print(f"Error fetching {ticker}: {e}. Using fallback.")  # Debug
            prices[ticker] = None  # Will fallback to avg_price in build_df
    return prices

def build_holdings_df(tickers, holdings):
    prices = fetch_live_prices(tickers)
    df_data = []
    for ticker in tickers:
        if ticker in holdings:
            h = holdings[ticker]
            ltp = prices.get(ticker, h['avg_price'])  # Fallback to avg if fetch fails
            invested = h['qty'] * h['avg_price']
            current_value = h['qty'] * ltp
            unrealized_pl = current_value - invested
            pct_chg = ((ltp - h['avg_price']) / h['avg_price']) * 100 if h['avg_price'] != 0 else 0
            df_data.append({
                'Ticker': ticker.replace('.NS', ''),
                'Net Qty': h['qty'],
                'Avg Price': h['avg_price'],
                'Live Price': ltp,
                'Invested': invested,
                'Current Value': current_value,
                'Unrealized P/L': unrealized_pl,
                '%Chg': pct_chg
            })
    df = pd.DataFrame(df_data)
    # Ensure numeric columns for proper sorting
    numeric_cols = ['Avg Price', 'Live Price', 'Invested', 'Current Value', 'Unrealized P/L', '%Chg']
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
    # Sort numerically by Current Value descending
    df = df.sort_values('Current Value', ascending=False)
    # Calculate Allocation %
    df['Allocation %'] = (df['Current Value'] / df['Current Value'].sum()) * 100
    return df, df.copy()  # Return numeric df and its copy

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

# Format for display (keep original df numeric for charts)
display_df = df.copy()
display_df['Avg Price'] = display_df['Avg Price'].apply(lambda x: f"{x:.2f}")
display_df['Live Price'] = display_df['Live Price'].apply(lambda x: f"{x:.2f}")
display_df['Invested'] = display_df['Invested'].apply(lambda x: f"{x:.2f}")
display_df['Current Value'] = display_df['Current Value'].apply(lambda x: f"{x:.2f}")
display_df['Unrealized P/L'] = display_df['Unrealized P/L'].apply(lambda x: f"{x:.2f}")
display_df['%Chg'] = display_df['%Chg'].apply(lambda x: f"{x:.2f}")
display_df['Allocation %'] = display_df['Allocation %'].apply(lambda x: f"{x:.2f}")
# Display the formatted DataFrame
st.dataframe(display_df)

# Charts
fig_pie = px.pie(df, values='Allocation %', names='Ticker', title='Allocation %')
st.plotly_chart(fig_pie)

# Bar Chart
fig_line = px.bar(df, x='Ticker', y='%Chg', title='Returns %')
st.plotly_chart(fig_line)

# Trend
multi_data = yf.download(tickers, period="1mo")['Close']
st.write("Trend Data:", multi_data)  # Debug
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
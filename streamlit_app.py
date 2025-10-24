import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
import time
from datetime import datetime, time
from collections import defaultdict

# ----------------------------------------------------------------------
# Page Config & Theme Toggle
# ----------------------------------------------------------------------
st.set_page_config(page_title="My Groww Portfolio Tracker", layout="wide")

theme = st.sidebar.selectbox("Theme", ["Light", "Dark"], index=0)
if theme == "Dark":
    st.markdown("<style>body {background-color: #0e1117; color: white;}</style>", unsafe_allow_html=True)
else:
    st.markdown("<style>body {background-color: white; color: black;}</style>", unsafe_allow_html=True)

st.title("My Groww Portfolio Tracker")


# ----------------------------------------------------------------------
# 1. Load & clean holdings from CSV
# ----------------------------------------------------------------------
def load_holdings():
    try:
        holdings_df = pd.read_csv('holdings.csv')
        holdings_df['quantity'] = pd.to_numeric(holdings_df['quantity'], errors='coerce')
        holdings_df['avg_price'] = pd.to_numeric(holdings_df['avg_price'], errors='coerce')

        bad_qty = holdings_df['quantity'].isna()
        bad_price = holdings_df['avg_price'].isna()
        if bad_qty.any() or bad_price.any():
            st.warning(f"Invalid data in holdings.csv: {bad_qty.sum()} bad qty, {bad_price.sum()} bad price")

        agg = defaultdict(lambda: {'total_qty': 0, 'total_cost': 0})
        for _, row in holdings_df.iterrows():
            if row['type'] == 'Buy':
                ticker = str(row['ticker']).strip().upper()
                qty = row['quantity']
                price = row['avg_price']
                if pd.notna(qty) and pd.notna(price):
                    agg[ticker]['total_qty'] += qty
                    agg[ticker]['total_cost'] += qty * price

        tickers = []
        holdings = {}
        for ticker, data in agg.items():
            if data['total_qty'] > 0:
                total_qty = data['total_qty']
                avg_price = data['total_cost'] / total_qty
                tickers.append(ticker)
                holdings[ticker] = {'qty': total_qty, 'avg_price': avg_price}

        return tickers, holdings

    except Exception as e:
        st.error(f"Error reading holdings.csv: {e}. Using sample data.")
        tickers = ['ADANIPOWER.NS']
        holdings = {'ADANIPOWER.NS': {'qty': 265, 'avg_price': 104.26}}
        return tickers, holdings


tickers, holdings = load_holdings()


# ----------------------------------------------------------------------
# 2. Market-open helper
# ----------------------------------------------------------------------
def is_market_open():
    now = datetime.now()
    return now.weekday() < 5 and time(9, 15) <= now.time() <= time(15, 30)


# ----------------------------------------------------------------------
# 3. Fetch live prices (robust + TATAMOTORS fix)
# ----------------------------------------------------------------------
@st.cache_data(ttl=30)
def fetch_live_prices(tickers):
    prices = {}
    all_tickers = tickers + ['^NSEI']

    for ticker in all_tickers:
        if 'TATAMOTORS' in ticker.upper():
            alt_tickers = ['TATAMOTORS.NS', 'TATAMOTORS.BO', 'TATAMOTORS']
        else:
            alt_tickers = [ticker]

        found = False
        for alt in alt_tickers:
            try:
                data = yf.Ticker(alt).history(period='1d', interval='1m' if is_market_open() else '1d')
                if not data.empty and 'Close' in data:
                    ltp = float(data['Close'].iloc[-1])
                    prices[ticker] = ltp
                    print(f"Success: {ticker} → {alt} = {ltp:.2f}")
                    found = True
                    break
            except:
                continue
        if not found:
            prices[ticker] = None
            print(f"Failed: {ticker}")

    return prices


# ----------------------------------------------------------------------
# 4. Build DataFrame + Nifty Benchmark (FIXED)
# ----------------------------------------------------------------------
def build_holdings_df(tickers, holdings):
    prices = fetch_live_prices(tickers)
    nifty_ltp = prices.get('^NSEI')

    # FIXED: Safe Nifty start price
    nifty_data = yf.Ticker('^NSEI').history(period='1d')
    nifty_start = nifty_data['Close'].iloc[0] if not nifty_data.empty else None
    nifty_change = ((nifty_ltp - nifty_start) / nifty_start * 100) if nifty_start and nifty_ltp else 0

    rows = []
    for ticker in tickers:
        if ticker not in holdings:
            continue
        h = holdings[ticker]
        qty = float(h['qty'])
        avg_price = float(h['avg_price'])
        ltp = prices.get(ticker)

        if ltp is None or pd.isna(ltp):
            st.warning(f"Live price unavailable for {ticker}. Using Avg ₹{avg_price:.2f}.")
            ltp = avg_price
            status = "Avg Fallback"
        else:
            ltp = float(ltp)
            status = "Live"

        invested = qty * avg_price
        current_value = qty * ltp
        unrealized_pl = current_value - invested
        pct_chg = ((ltp - avg_price) / avg_price) * 100 if avg_price != 0 else 0.0

        rows.append({
            'Ticker': ticker.replace('.NS', ''),
            'Net Qty': qty,
            'Avg Price': avg_price,
            'Live Price': ltp,
            'Invested': invested,
            'Current Value': current_value,
            'Unrealized P/L': unrealized_pl,
            '%Chg': pct_chg,
            'Status': status
        })

    df = pd.DataFrame(rows)
    numeric_cols = ['Avg Price', 'Live Price', 'Invested', 'Current Value', 'Unrealized P/L', '%Chg', 'Net Qty']
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')

    total_current = df['Current Value'].sum()
    df['Allocation %'] = (df['Current Value'] / total_current * 100).round(2)
    df = df.sort_values('Current Value', ascending=False).reset_index(drop=True)
    df_numeric = df.copy()

    return df, df_numeric, nifty_change


# ----------------------------------------------------------------------
# 5. Auto-refresh
# ----------------------------------------------------------------------
if 'last_update' not in st.session_state:
    st.session_state.last_update = datetime.now()

st.sidebar.title("Controls")
if st.sidebar.button("Manual Refresh"):
    st.session_state.last_update = datetime.now()
    st.rerun()

if (datetime.now() - st.session_state.last_update).total_seconds() >= 30:
    st.session_state.last_update = datetime.now()
    st.rerun()


# ----------------------------------------------------------------------
# 6. Dashboard
# ----------------------------------------------------------------------
df, df_numeric, nifty_change = build_holdings_df(tickers, holdings)

# Pretty display
display_df = df.copy()
fmt_cols = ['Avg Price', 'Live Price', 'Invested', 'Current Value', 'Unrealized P/L', '%Chg', 'Allocation %']
for c in fmt_cols:
    display_df[c] = display_df[c].apply(lambda x: f"{x:.2f}")

st.dataframe(display_df, use_container_width=True)

# Export Button
excel_data = df.copy()
st.download_button(
    label="Download Portfolio as Excel",
    data=excel_data.to_csv(index=False).encode(),
    file_name=f"portfolio_{datetime.now().strftime('%Y%m%d')}.csv",
    mime="text/csv"
)

# Charts
col1, col2 = st.columns(2)
with col1:
    fig_pie = px.pie(df, values='Allocation %', names='Ticker', title='Portfolio Allocation')
    st.plotly_chart(fig_pie, use_container_width=True)
with col2:
    fig_bar = px.bar(df, x='Ticker', y='%Chg', title='Returns %', color='%Chg', color_continuous_scale='RdYlGn')
    st.plotly_chart(fig_bar, use_container_width=True)

# Trend
try:
    trend_data = yf.download(tickers + ['^NSEI'], period="1mo", progress=False)['Close']
    fig_trend = px.line(trend_data, title='1-Month Trend vs Nifty 50')
    st.plotly_chart(fig_trend, use_container_width=True)
except:
    st.warning("Trend chart unavailable")

# Metrics
status = " (Live)" if is_market_open() else " (Closed)"
st.caption(f"Updated: {st.session_state.last_update.strftime('%Y-%m-%d %H:%M:%S')}{status}")

total_invested = df_numeric['Invested'].sum()
total_value = df_numeric['Current Value'].sum()
total_return_pct = (df_numeric['Unrealized P/L'].sum() / total_invested * 100) if total_invested != 0 else 0.0

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Return", f"{total_return_pct:+.2f}%", delta=f"{total_return_pct:+.2f}%")
with col2:
    st.metric("Portfolio Value", f"₹{total_value:,.2f}")
with col3:
    st.metric("Nifty 50", f"{nifty_change:+.2f}%", delta=f"{nifty_change:+.2f}%")
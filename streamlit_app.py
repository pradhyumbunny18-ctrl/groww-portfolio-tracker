import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from datetime import datetime, time
from collections import defaultdict

st.set_page_config(page_title="My Groww Portfolio Tracker", layout="wide")
st.title("My Groww Portfolio Tracker")


# ----------------------------------------------------------------------
# 1. Load & clean holdings from CSV
# ----------------------------------------------------------------------
def load_holdings():
    try:
        holdings_df = pd.read_csv('holdings.csv')

        # ---- Force numeric on the raw columns ----
        holdings_df['quantity'] = pd.to_numeric(holdings_df['quantity'], errors='coerce')
        holdings_df['avg_price'] = pd.to_numeric(holdings_df['avg_price'], errors='coerce')

        # ---- Warn about bad rows ----
        bad_qty = holdings_df['quantity'].isna()
        bad_price = holdings_df['avg_price'].isna()
        if bad_qty.any() or bad_price.any():
            st.warning(
                f"Some rows in holdings.csv have invalid numbers:\n"
                f"• Bad quantity: {bad_qty.sum()} rows\n"
                f"• Bad avg_price: {bad_price.sum()} rows"
            )

        # ---- Aggregate buys only ----
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
# 3. Fetch live prices (robust)
# ----------------------------------------------------------------------
def fetch_live_prices(tickers):
    prices = {}
    for ticker in tickers:
        try:
            data = yf.Ticker(ticker).history(
                period='1d',
                interval='1m' if is_market_open() else '1d',
                prepost=True
            )
            if not data.empty:
                ltp = float(data['Close'].iloc[-1])
                prices[ticker] = ltp
                print(f"Fetched {ticker}: {ltp:.2f}")
            else:
                raise ValueError("Empty dataframe")
        except Exception as e:
            print(f"Failed {ticker}: {e}")
            prices[ticker] = None
    return prices


# ----------------------------------------------------------------------
# 4. Build the main DataFrame (SAFE)
# ----------------------------------------------------------------------
def build_holdings_df(tickers, holdings):
    live_prices = fetch_live_prices(tickers)

    rows = []
    for ticker in tickers:
        if ticker not in holdings:
            continue

        h = holdings[ticker]

        # ---- Ensure qty & avg_price are float ----
        qty = float(h['qty'])
        avg_price = float(h['avg_price'])

        # ---- Live price with fallback ----
        ltp = live_prices.get(ticker)
        if ltp is None or pd.isna(ltp):
            st.warning(f"Live price unavailable for {ticker}. Using Avg Price.")
            ltp = avg_price
        else:
            ltp = float(ltp)

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
            '%Chg': pct_chg
        })

    df = pd.DataFrame(rows)

    # ---- Numeric conversion (safe) ----
    numeric_cols = ['Avg Price', 'Live Price', 'Invested',
                    'Current Value', 'Unrealized P/L', '%Chg', 'Net Qty']
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')

    # ---- Allocation % (after numeric) ----
    total_current = df['Current Value'].sum()
    df['Allocation %'] = (df['Current Value'] / total_current * 100).round(2)

    # ---- Sort by Current Value descending ----
    df = df.sort_values('Current Value', ascending=False).reset_index(drop=True)

    # Return a clean numeric copy for charts/metrics
    df_numeric = df.copy()
    return df, df_numeric


# ----------------------------------------------------------------------
# 5. Auto-refresh logic
# ----------------------------------------------------------------------
if 'last_update' not in st.session_state:
    st.session_state.last_update = datetime.now()

st.sidebar.title("Controls")
if st.sidebar.button("Manual Refresh"):
    st.session_state.last_update = datetime.now()
    st.rerun()

# Auto-refresh every 30 seconds
if (datetime.now() - st.session_state.last_update).total_seconds() >= 30:
    st.session_state.last_update = datetime.now()
    st.rerun()


# ----------------------------------------------------------------------
# 6. Build dashboard
# ----------------------------------------------------------------------
df, df_numeric = build_holdings_df(tickers, holdings)

# ---- Pretty display (strings) ----
display_df = df.copy()
fmt_cols = ['Avg Price', 'Live Price', 'Invested', 'Current Value',
            'Unrealized P/L', '%Chg', 'Allocation %']
for c in fmt_cols:
    display_df[c] = display_df[c].apply(lambda x: f"{x:.2f}")

st.dataframe(display_df, use_container_width=True)


# ---- Charts ----
fig_pie = px.pie(df, values='Allocation %', names='Ticker',
                 title='Portfolio Allocation %')
st.plotly_chart(fig_pie, use_container_width=True)

fig_bar = px.bar(df, x='Ticker', y='%Chg', title='Returns % by Stock',
                 color='%Chg', color_continuous_scale='RdYlGn')
st.plotly_chart(fig_bar, use_container_width=True)

# 1-month trend
try:
    trend_data = yf.download(tickers, period="1mo", progress=False)['Close']
    fig_trend = px.line(trend_data, title='1-Month Price Trend')
    st.plotly_chart(fig_trend, use_container_width=True)
except Exception as e:
    st.warning(f"Trend chart unavailable: {e}")


# ---- Metrics ----
status = " (Live)" if is_market_open() else " (Closed - Last Close)"
st.caption(f"Updated: {st.session_state.last_update.strftime('%Y-%m-%d %H:%M:%S')}{status}")

total_invested = df_numeric['Invested'].sum()
total_value = df_numeric['Current Value'].sum()
total_return_pct = (df_numeric['Unrealized P/L'].sum() / total_invested * 100) \
    if total_invested != 0 else 0.0

col1, col2 = st.columns(2)
with col1:
    st.metric("Total Return", f"{total_return_pct:+.2f}%")
with col2:
    st.metric("Portfolio Value", f"₹{total_value:,.2f}")
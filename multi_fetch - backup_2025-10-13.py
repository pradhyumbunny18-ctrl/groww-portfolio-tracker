import yfinance as yf
import pandas as pd

tickers = ["TCS.NS", "INFY.NS", "HDFCBANK.NS", "RELIANCE.NS", "TATAMOTORS.NS", "AAPL", "TSLA", "PFE"]

data = {}
for ticker in tickers:
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        latest_close = hist['Close'].iloc[-1]
        data[ticker] = round(latest_close, 2)
        print(f"{ticker}: {latest_close:.2f} (as of {hist.index[-1].date()})")
    except Exception as e:
        print(f"Error for {ticker}: {e}")

df = pd.DataFrame(list(data.items()), columns=['Ticker', 'Latest_Price'])
print("\n--- Portfolio Price Snapshot ---")
print(df.to_string(index=False))
df.to_csv('live_prices.csv', index=False)
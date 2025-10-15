import yfinance as yf

stock = yf.Ticker("RELIANCE.NS")
data = stock.history(period="5d")

print("Reliance Stock Data (Last 5 Days):")
print(data[['Open', 'High', 'Low', 'Close', 'Volume']])
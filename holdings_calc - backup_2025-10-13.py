import pandas as pd
import yfinance as yf

# Load your Groww CSV
holdings = pd.read_csv('holdings.csv')

# Group: Net qty (Buys - Sells), avg price (Buys only)
grouped = holdings.groupby('ticker').agg({
    'quantity': lambda x: x[holdings['type'] == 'Buy'].sum() - x[holdings['type'] == 'Sell'].sum(),
    'avg_price': lambda x: (x[holdings['type'] == 'Buy'] * holdings[holdings['type'] == 'Buy']['quantity']).sum() / holdings[holdings['type'] == 'Buy']['quantity'].sum()
}).reset_index()
grouped.columns = ['Ticker', 'Net_Qty', 'Avg_Price']

# Fetch live prices
tickers = grouped['Ticker'].tolist()
live_prices = {}
for t in tickers:
    live_prices[t] = yf.Ticker(t).history(period="1d")['Close'].iloc[-1]

# Calcs: Invested, Current Value, P/L, Return %, Allocation
grouped['Live_Price'] = grouped['Ticker'].map(live_prices)
grouped['Invested'] = grouped['Net_Qty'] * grouped['Avg_Price']
grouped['Current_Value'] = grouped['Net_Qty'] * grouped['Live_Price']
grouped['Unrealized_PL'] = grouped['Current_Value'] - grouped['Invested']
grouped['Return_Pct'] = (grouped['Unrealized_PL'] / grouped['Invested']) * 100
grouped['Allocation_Pct'] = (grouped['Current_Value'] / grouped['Current_Value'].sum()) * 100

print("Portfolio Holdings & P/L:\n", grouped.round(2))
total_invested = grouped['Invested'].sum()
total_value = grouped['Current_Value'].sum()
print(f"\nTotal Invested: ₹{total_invested:.2f} | Total Value: ₹{total_value:.2f} | Portfolio Return: {((total_value - total_invested)/total_invested*100):.2f}%")
grouped.to_csv('portfolio_summary.csv', index=False)  # Save for dashboard
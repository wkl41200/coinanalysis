import pandas as pd
import plotly.graph_objects as go

# --- Load data ---
ohlc = pd.read_csv(r"C:\Users\Duncan Wan\Desktop\VSCODE\4hrs\future\cleaned\BTCUSDT_4h_2024_all.csv", parse_dates=["open_time"])  # columns: time, open, high, low, close, volume
trades = pd.read_csv(r"C:\Users\Duncan Wan\Desktop\VSCODE\fundingOI\result.csv", parse_dates=["entry_time", "exit_time"])

# Align timezones if needed (ensure both in UTC)
ohlc = ohlc.sort_values("open_time")

# --- Build figure ---
fig = go.Figure(data=[go.Candlestick(
    x=ohlc["open_time"], open=ohlc["open"], high=ohlc["high"], low=ohlc["low"], close=ohlc["close"],
    name="Price"
)])

# Entry markers
fig.add_trace(go.Scatter(
    x=trades["entry_time"], y=trades["entry_price"],
    mode="markers", name="Entry",
    marker=dict(symbol="triangle-up", size=10),
    text=(trades["side"] + " | " + trades["exit_reason"].astype(str)),
    hovertemplate="Entry: %{x}<br>Price: %{y}<br>%{text}<extra></extra>"
))

# Exit markers
fig.add_trace(go.Scatter(
    x=trades["exit_time"], y=trades["exit_price"],
    mode="markers", name="Exit",
    marker=dict(symbol="triangle-down", size=10),
    text=("PnL Total: $" + trades["pnl_total_usd"].round(2).astype(str)),
    hovertemplate="Exit: %{x}<br>Price: %{y}<br>%{text}<extra></extra>"
))

fig.update_layout(title="Trades overlay", xaxis_rangeslider_visible=False, legend=dict(orientation="h"))
fig.show()


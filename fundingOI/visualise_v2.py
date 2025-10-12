import pandas as pd
import numpy as np
from plotly.subplots import make_subplots
import plotly.graph_objects as go

# -------------------- Load & normalize --------------------
ohlc = pd.read_csv(r"C:\Users\Duncan Wan\Desktop\VSCODE\4hrs\future\cleaned\BTCUSDT_4h_2024_all.csv")
# rename time column to 'time' then parse
time_col = next(c for c in ["time","open_time","bar_end","datetime","date","timestamp"] if c in ohlc.columns)
ohlc = ohlc.rename(columns={time_col:"time"})
ohlc["time"] = pd.to_datetime(ohlc["time"], utc=True, errors="coerce")
ohlc = ohlc.sort_values("time")

trades = pd.read_csv(r"C:\Users\Duncan Wan\Desktop\VSCODE\fundingOI\result.csv")
trades.rename(columns={
    "entry_time_utc":"entry_time",
    "exit_time_utc":"exit_time",
    "entry_price_usd":"entry_price",
    "exit_price_usd":"exit_price",
}, inplace=True)
trades["entry_time"] = pd.to_datetime(trades["entry_time"], utc=True, errors="coerce")
trades["exit_time"]  = pd.to_datetime(trades["exit_time"],  utc=True, errors="coerce")
trades = trades.sort_values("entry_time").reset_index(drop=True)
trades["trade_id"] = np.arange(1, len(trades)+1)
trades["pnl_color"] = np.where(trades["pnl_total_usd"]>0, "green", "red")
trades["side_symbol"] = np.where(trades["side"].str.upper().str.startswith("L"), "triangle-up", "triangle-down")
trades["hold_bars"] = ((trades["exit_time"] - trades["entry_time"]) / pd.Timedelta(hours=4)).astype("float")

# Optional: driver series (funding/open interest). If not present, comment this block out.
driver = None
for cand in ["funding","funding_rate","funding_pct","oi","open_interest"]:
    if cand in ohlc.columns:
        driver = cand
        break

# -------------------- Filters (edit as you like) --------------------
# example filters to quickly trim noise; tweak or remove
SIDE_FILTER = ["LONG","SHORT"]          # or ["LONG"] etc.
MIN_ABS_PNL = 0                         # e.g., 50 to only show exits with > $50 PnL
REASONS_KEEP = None                     # e.g., {"time_stop","struct_stop"}; None = all
DATE_FROM, DATE_TO = None, None         # e.g., "2024-11-01", "2025-03-01"

t = trades.copy()
t = t[t["side"].str.upper().isin([s.upper() for s in SIDE_FILTER])]
t = t[np.abs(t["pnl_total_usd"]) >= MIN_ABS_PNL]
if REASONS_KEEP:
    t = t[t["exit_reason"].astype(str).isin(REASONS_KEEP)]
if DATE_FROM: t = t[t["entry_time"] >= pd.Timestamp(DATE_FROM, tz="UTC")]
if DATE_TO:   t = t[t["entry_time"] <= pd.Timestamp(DATE_TO,   tz="UTC")]

# -------------------- Equity curve --------------------
t_eq = t.sort_values("exit_time").copy()
t_eq["equity"] = t_eq["pnl_total_usd"].cumsum()

# -------------------- Figure layout --------------------
rows = 3 if driver is not None else 2
fig = make_subplots(
    rows=rows, cols=1, shared_xaxes=True,
    row_heights=[0.65, 0.20, 0.15][:rows],
    vertical_spacing=0.03,
    subplot_titles=("Price & Trades", "Equity Curve") + ((driver,) if driver else tuple())
)

# Candles
fig.add_trace(go.Candlestick(
    x=ohlc["time"], open=ohlc["open"], high=ohlc["high"], low=ohlc["low"], close=ohlc["close"],
    name="Price", increasing_line_color="#2ca02c", decreasing_line_color="#d62728"
), row=1, col=1)

# Entries
fig.add_trace(go.Scatter(
    x=t["entry_time"], y=t["entry_price"], mode="markers", name="Entry",
    marker=dict(symbol=t["side_symbol"], size=9, line=dict(width=0.5, color="black"), color="dodgerblue"),
    text=("ID " + t["trade_id"].astype(str) + " | " + t["side"].astype(str) +
          " | hold " + t["hold_bars"].round(1).astype(str) + " bars"),
    hovertemplate="Entry %{x}<br>Price %{y}<br>%{text}<extra></extra>"
), row=1, col=1)

# Exits (colored by PnL)
fig.add_trace(go.Scatter(
    x=t["exit_time"], y=t["exit_price"], mode="markers", name="Exit",
    marker=dict(symbol="x", size=8, color=t["pnl_color"]),
    text=("ID " + t["trade_id"].astype(str) + " | PnL $" + t["pnl_total_usd"].round(2).astype(str) +
          " | reason " + t["exit_reason"].astype(str)),
    hovertemplate="Exit %{x}<br>Price %{y}<br>%{text}<extra></extra>"
), row=1, col=1)

# Connect entry->exit with faint lines (cap to avoid too many traces)
MAX_LINES = 600
if len(t) <= MAX_LINES:
    fig.add_trace(go.Scatter(
        x=np.r_[t["entry_time"].values, t["exit_time"].values, [None]*len(t)],
        y=np.r_[t["entry_price"].values, t["exit_price"].values, [None]*len(t)],
        mode="lines",
        name="Trade path",
        line=dict(width=0.5, color="rgba(0,0,0,0.25)")
    ), row=1, col=1)

# Equity curve
fig.add_trace(go.Scatter(
    x=t_eq["exit_time"], y=t_eq["equity"], mode="lines+markers",
    name="Equity", marker=dict(size=4)
), row=2, col=1)

# Driver subplot (funding/OI) if available
if driver is not None:
    fig.add_trace(go.Scatter(
        x=ohlc["time"], y=ohlc[driver], mode="lines", name=driver
    ), row=3, col=1)

# X-axis tools
fig.update_layout(
    title="Trades overlay",
    xaxis_rangeslider_visible=False,
    legend=dict(orientation="h"),
    hovermode="x unified",
    xaxis=dict(rangeselector=dict(
        buttons=list([
            dict(count=1, label="1m", step="month", stepmode="backward"),
            dict(count=3, label="3m", step="month", stepmode="backward"),
            dict(count=6, label="6m", step="month", stepmode="backward"),
            dict(count=1, label="YTD", step="year", stepmode="todate"),
            dict(step="all")
        ])
    ))
)

fig.show()

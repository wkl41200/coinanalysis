import numpy as np
import pandas as pd




def backtest_funding_multi(
    df_in: pd.DataFrame,
    # column names
    price_col="prep_close",
    high_col="perp_high",   #high of bar (we do not have both of this) -> can consider adding it
    low_col ="perp_low",    #low of bar 
    fund_col="funding_rate",
    # funding/premium
    base_per_8h = 1e-4,        # 0.01% per 8h (Binance-style)
    pct_win = 90,              # we look at funding at last 90 bars? (6 bar per day so 15 days back?)
    p_hi = 0.90, p_lo = 0.1,  # extremes as percentiles of premium (extreme percentile)
    # context windows (past-only)
    roll_high_n = 24,          # price 24-bar high for tops (4 days)
    fund_low_n  = 18,          # funding 18-bar low for bottoms (3 days)
    # stop-entry trigger
    stopentry_buffer = 0.0002, # 0.05% buffer around prior high/low # dont eneter immediately when 
    # exits (structure + safety)
    pivot_k = 6,               # swing-pivot lookback
    struct_buffer = 0.005,     # 0.5% beyond pivot
    struct_confirm_closes = 2, # 2 consecutive closes beyond stop to exit
    struct_grace_bars = 2,     # ignore structure stop first N bars
    fresh_low_lookahead = 3,   # long invalidation: fresh funding low within N bars
    time_stop_settlements = 2, # exit after N settlements if nothing else
    cat_stop_pct = 0.065,      # 6.5% catastrophe stop
    # entry throttles
    dedup_bars = 12,           # per-side de-dup (min bars between same-side entries)
    # execution & costs
    notional_usd = 10_000.0,   # fixed notional per trade
    taker_fee = 0.0004,        # 0.04% per side
    settlement_hours=(0,8,16), # 8h funding schedule (UTC)
):
    """
    Multi-position backtester: every valid signal opens a NEW independent trade.
    Returns (log: DataFrame of closed trades, stats: dict)
    """
    # ---------- prep ----------
    df = df_in.copy()

    # require datetime index
    if not pd.api.types.is_datetime64_any_dtype(df.index):
        raise ValueError("Index must be datetime (UTC). Do df.set_index('bar_time') first.")

    df = df.sort_index()

    # Ensure price/high/low columns exist (proxy high/low with price if missing)
    if high_col not in df.columns: df[high_col] = df[price_col]
    if low_col  not in df.columns: df[low_col]  = df[price_col]

    PX, HI, LO, FR = price_col, high_col, low_col, fund_col

    # settlement mask
    df["is_settle"] = df.index.hour.isin(settlement_hours) & (df.index.minute == 0)

    # funding premium & rolling percentile bands
    df["fund_premium"] = df[FR] - base_per_8h
    roll = df["fund_premium"].rolling(pct_win, min_periods=pct_win)
    df["p_hi"] = roll.quantile(p_hi)
    df["p_lo"] = roll.quantile(p_lo)

    # past-only context (NO look-ahead)
    df["roll_high_prev_24"] = df[PX].shift(1).rolling(roll_high_n, min_periods=roll_high_n).max()
    df["fund_low_prev_18"]  = df["fund_premium"].shift(1).rolling(fund_low_n, min_periods=fund_low_n).min()

    # setups (arm ideas at close of THIS bar; fill on next bar)
    setup_short = (df["fund_premium"] >= df["p_hi"]) & (df[PX] >= df["roll_high_prev_24"])
    setup_long  = (df["fund_premium"] <= df["p_lo"])  | (df["fund_premium"] <= df["fund_low_prev_18"])

    # stop-entry levels from prior bar
    prior_low  = df[LO].shift(1)
    prior_high = df[HI].shift(1)
    stop_short_lvl = prior_low  * (1 - stopentry_buffer)  # sell-stop to short
    stop_long_lvl  = prior_high * (1 + stopentry_buffer)  # buy-stop to long

    df["volume_ratio"] = df["perp_vol"] / df["perp_vol"].rolling(20).mean()

    immediate_entry = setup_long.shift(1) & (df["volume_ratio"] > 2.0)
    stop_entry = setup_long.shift(1) & (df[HI] >= stop_long_lvl.shift(1)) & ~immediate_entry

    

    # arm now, fill on next bar if crossed
    short_fill = setup_short.shift(1) & (df[LO]  <= stop_short_lvl.shift(1))
    long_fill = immediate_entry | stop_entry

    entry_px_short = stop_short_lvl.shift(1).where(short_fill)
    entry_px_long  = stop_long_lvl.shift(1).where(long_fill)


    # precompute invalidation helpers
    pinned_hi = df["is_settle"] & (df["fund_premium"] >= df["p_hi"] - 1e-12)
    fresh_low = df["fund_premium"] < df["fund_low_prev_18"] - 1e-12

    # small helpers
    def _pivot_high(i):
        j0 = max(0, i - pivot_k)
        return float(df[HI].iloc[j0:i+1].max())
    def _pivot_low(i):
        j0 = max(0, i - pivot_k)
        return float(df[LO].iloc[j0:i+1].min())

    # ---------- multi-position engine ----------
    trades = []              # closed trades
    open_trades = []         # active trades (list of dicts)
    last_entry_i_side = {"LONG": -10_000, "SHORT": -10_000}  # per-side de-dup

    idx, N = df.index, len(df)

    for i in range(1, N):
        # 1) funding accrual for every open trade at PREVIOUS settlement
        if df["is_settle"].iloc[i-1]:
            fr_prev = float(df[FR].iloc[i-1])
            for t in open_trades:
                side_mult = +1.0 if t["side"] == "LONG" else -1.0
                t["fund_usd"] += fr_prev * notional_usd * side_mult

        # 2) entries — create NEW trades even if others already exist
        if pd.notna(entry_px_short.iloc[i]) and (i - last_entry_i_side["SHORT"] >= dedup_bars):
            px_e = float(entry_px_short.iloc[i])
            open_trades.append({
                "side": "SHORT",
                "entry_px": px_e,
                "entry_i": i,
                "entry_time": idx[i],
                "entry_high": float(df[HI].iloc[i]),
                "entry_low":  float(df[LO].iloc[i]),
                "fund_usd": 0.0,
                "entry_fee": taker_fee * notional_usd,
                "closes_beyond": 0,
                "struct_stop": max(_pivot_high(i-1)*(1+struct_buffer), px_e*(1+struct_buffer/2)),
            })
            last_entry_i_side["SHORT"] = i

        if pd.notna(entry_px_long.iloc[i]) and (i - last_entry_i_side["LONG"] >= dedup_bars):
            px_e = float(entry_px_long.iloc[i])
            open_trades.append({
                "side": "LONG",
                "entry_px": px_e,
                "entry_i": i,
                "entry_time": idx[i],
                "entry_high": float(df[HI].iloc[i]),
                "entry_low":  float(df[LO].iloc[i]),
                "fund_usd": 0.0,
                "entry_fee": taker_fee * notional_usd,
                "closes_beyond": 0,
                "struct_stop": min(_pivot_low(i-1)*(1-struct_buffer), px_e*(1-struct_buffer/2)),
            })
            last_entry_i_side["LONG"] = i

        # 3) exits — evaluate each open trade
        price_close = float(df[PX].iloc[i])
        price_high  = float(df[HI].iloc[i])
        price_low   = float(df[LO].iloc[i])
        is_settle   = bool(df["is_settle"].iloc[i])

        # iterate backwards so removals are safe
        for k in range(len(open_trades)-1, -1, -1):
            t = open_trades[k]
            exit_reason = None

            # catastrophe stop (intrabar)
            if t["side"] == "SHORT" and price_high >= t["entry_px"] * (1 + cat_stop_pct):
                exit_reason = "cat_short"
            if t["side"] == "LONG" and price_low  <= t["entry_px"] * (1 - cat_stop_pct):
                exit_reason = "cat_long"

            # structure stop with grace & 2-close confirm
            if exit_reason is None and (i - t["entry_i"]) >= struct_grace_bars:
                if t["side"] == "SHORT":
                    if price_close > t["struct_stop"]:
                        t["closes_beyond"] += 1
                    else:
                        t["closes_beyond"] = 0
                    if t["closes_beyond"] >= struct_confirm_closes:
                        exit_reason = "struct_short"
                else:
                    if price_close < t["struct_stop"]:
                        t["closes_beyond"] += 1
                    else:
                        t["closes_beyond"] = 0
                    if t["closes_beyond"] >= struct_confirm_closes:
                        exit_reason = "struct_long"

            # funding-behaviour invalidation
            if exit_reason is None:
                settles_since = int(df["is_settle"].iloc[t["entry_i"]:i+1].sum())
                if t["side"] == "SHORT":
                    pinned_count = int(pinned_hi.iloc[t["entry_i"]:i+1].sum())
                    made_higher_high = price_high > t["entry_high"]
                    if pinned_count >= 2 and made_higher_high:
                        exit_reason = "cap_persist"
                else:
                    fresh_low_now = bool(fresh_low.iloc[max(t["entry_i"], i - fresh_low_lookahead + 1):i+1].any())
                    made_lower_low = price_low < t["entry_low"]
                    if fresh_low_now and made_lower_low:
                        exit_reason = "fresh_low_cont"

                # time stop after N settlements (long needs reclaim)
                if exit_reason is None and settles_since >= time_stop_settlements:
                    if t["side"] == "SHORT":
                        exit_reason = "time_short"
                    else:
                        if price_close <= t["entry_high"]:
                            exit_reason = "time_long_no_reclaim"

            # execute exit
            if exit_reason is not None:
                fund_usd = t["fund_usd"]
                if is_settle:
                    side_mult = +1.0 if t["side"] == "LONG" else -1.0
                    fund_usd += float(df[FR].iloc[i]) * notional_usd * side_mult

                side_mult = +1.0 if t["side"] == "LONG" else -1.0
                pnl_price_usd = notional_usd * side_mult * ((price_close / t["entry_px"]) - 1.0)
                exit_fee_usd  = taker_fee * notional_usd
                pnl_total_usd = pnl_price_usd + fund_usd - (t["entry_fee"] + exit_fee_usd)

                trades.append({
                    "entry_time": t["entry_time"],
                    "side": t["side"],
                    "entry_price": t["entry_px"],
                    "exit_time": idx[i],
                    "exit_price": price_close,
                    "bars_held": int(i - t["entry_i"]),
                    "pnl_price_usd": float(pnl_price_usd),
                    "funding_usd": float(fund_usd),
                    "fees_usd": float(-(t["entry_fee"] + exit_fee_usd)),
                    "pnl_total_usd": float(pnl_total_usd),
                    "exit_reason": exit_reason
                })
                del open_trades[k]

    # 4) close anything left at the end
    if len(open_trades):
        price_close = float(df[PX].iloc[-1])
        is_settle   = bool(df["is_settle"].iloc[-1])
        for t in open_trades:
            fund_usd = t["fund_usd"]
            if is_settle:
                side_mult = +1.0 if t["side"] == "LONG" else -1.0
                fund_usd += float(df[FR].iloc[-1]) * notional_usd * side_mult

            side_mult = +1.0 if t["side"] == "LONG" else -1.0
            pnl_price_usd = notional_usd * side_mult * ((price_close / t["entry_px"]) - 1.0)
            exit_fee_usd  = taker_fee * notional_usd
            pnl_total_usd = pnl_price_usd + fund_usd - (t["entry_fee"] + exit_fee_usd)

            trades.append({
                "entry_time": t["entry_time"],
                "side": t["side"],
                "entry_price": t["entry_px"],
                "exit_time": df.index[-1],
                "exit_price": price_close,
                "bars_held": int(len(df)-1 - t["entry_i"]),
                "pnl_price_usd": float(pnl_price_usd),
                "funding_usd": float(fund_usd),
                "fees_usd": float(-(t["entry_fee"] + exit_fee_usd)),
                "pnl_total_usd": float(pnl_total_usd),
                "exit_reason": "eod_close"
            })

    log = pd.DataFrame(trades).sort_values("entry_time").reset_index(drop=True)

    # ---------- stats ----------
    if len(log):
        pnl = log["pnl_total_usd"].values
        gp = log.loc[log["pnl_total_usd"]>0,"pnl_total_usd"].sum()
        gl = -log.loc[log["pnl_total_usd"]<0,"pnl_total_usd"].sum()
        eq = log["pnl_total_usd"].cumsum()
        max_dd = float((eq.cummax() - eq).max())
        stats = {
            "trades": int(len(log)),
            "win_rate": float((pnl>0).mean()),
            "expectancy_usd": float(np.mean(pnl)),
            "median_usd": float(np.median(pnl)),
            "profit_factor": float(gp/gl) if gl>0 else np.inf,
            "total_pnl_usd": float(np.sum(pnl)),
            "max_dd_usd": max_dd,
        }
    else:
        stats = {"trades":0, "win_rate":np.nan, "expectancy_usd":np.nan,
                 "median_usd":np.nan, "profit_factor":np.nan,
                 "total_pnl_usd":0.0, "max_dd_usd":0.0}

    return log, stats


# 1) load your CSV once (example)
df = pd.read_csv('/Users/duncanwan/Desktop/learning/Bitcoin/4hrs/BTC_combined_2024_v2.csv')


# if your file has a bar_time column:
df["bar_time"] = pd.to_datetime(df["bar_time"], utc=True)
df = df.set_index("bar_time").sort_index()

# 2) run
log, stats = backtest_funding_multi(df, notional_usd=10_000.0)
print(stats)

log.to_csv('result_v2.csv', index=False)


log.groupby("side")[["pnl_price_usd","funding_usd","pnl_total_usd"]].sum()

cols = ["entry_time","exit_time","side","entry_price","exit_price",
        "bars_held","pnl_price_usd","funding_usd","fees_usd","pnl_total_usd"]
top10 = log.sort_values("pnl_total_usd", ascending=False).head(10)[cols]

worst10 = log.sort_values("pnl_total_usd", ascending=True).head(10)[cols]
print(worst10)
pd.options.display.float_format = "{:,.2f}".format
print(top10.reset_index(drop=True))
print(worst10.reset_index(drop=True))
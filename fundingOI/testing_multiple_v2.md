def backtest_funding_multi(
    df_in: pd.DataFrame,
    # column names
    price_col="prep_close",
    high_col="perp_high",   #high of bar (we do not have both of this) -> can consider adding it
    low_col ="perp_low",    #low of bar 
    fund_col="funding_rate",


#potentially we will need to adjust on here
    base_per_8h = 1e-4,        # 0.01% per 8h (Binance-style)
    pct_win = 90,              # we look at funding at last 90 bars? (6 bar per day so 15 days back?)
    p_hi = 0.90, p_lo = 0.1,  # extremes as percentiles of premium (extreme percentile)
  


  Past data only (context)
    roll_high_n = 24,          # price 24-bar high for tops (4 days)
    fund_low_n  = 18,          # funding 18-bar low for bottoms (3 days)
    # stop-entry trigger
    stopentry_buffer = 0.0005, # 0.05% buffer around prior high/low - so we dont entry when it hit, we wait for price to move another 0.0005?
                                e.g SHORT -> price to break below previous's bar low by 0.05%?
                                e.g LONG -> price to break above previous's bar high by 0.05%?
   so for ENTRY -> when signal appear, 



    # exits (structure + safety)
    pivot_k = 6,               # swing-pivot lookback. (Your stop loss is based on the highest/lowest point in the last 6 bars)
    struct_buffer = 0.005,     # 0.5% beyond pivot (Place stop 0.5% beyond the pivot)
    struct_confirm_closes = 2, # 2 consecutive closes beyond stop to exit (Don't exit on one spike. Need 2 consecutive bar closes beyond the stop.)
    struct_grace_bars = 2,     # ignore structure stop first N bars ( Give the trade 2 bars (8 hours) to "breathe" before the structure stop activates)
                            # basically giving the position to run for minimum 8hours/2bars/0.3days to run (this is a problem as we see a lot of them enter and stopped)

    fresh_low_lookahead = 3,   # long invalidation: fresh funding low within N bars
                            #if long, funding make NEW LOW + NEW LOWER LOW (in next 3 bars), EXIT (THIS IS ANOTHER PROBLEM)

    time_stop_settlements = 2, # exit after N settlements if nothing else
    cat_stop_pct = 0.065,      # 6.5% catastrophe stop (Emergency stop if price moves 6.5% against you INTRABAR)??? this is protect my position but need to redefine
                        #BLOW UP PROTECTION

    # entry throttles (the engine?)
    dedup_bars = 12,           # per-side de-dup (min bars between same-side entries)
                            # is this a problem? 

    # execution & costs
    notional_usd = 10_000.0,   # fixed notional per trade
    taker_fee = 0.0004,        # 0.04% per side
    settlement_hours=(0,8,16), # 8h funding schedule (UTC)





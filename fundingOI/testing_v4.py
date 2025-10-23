# testing 1.  volume confirmation   2. remove shorts   3. wider stop loss 

import pandas as pd
import numpy as np

"""
QUICK IMPROVEMENT TEST
Goal: Test 3 simple improvements in ONE script
Time: 5 minutes to run, immediate results
No new data needed, no complex analysis
"""

# ============ CONFIGURATION ============
CSV_PATH = 'BTC_perp_funding_combined_OHLC.csv'

EXTREME_LOW_FUNDING = 0.00003
PRICE_BUFFER_PCT = 0.03
MIN_BARS_BETWEEN_ENTRIES = 6
TAKER_FEE = 0.0004
TRADING_FEE_ROUND_TRIP = TAKER_FEE * 2

# ============ LOAD DATA ============
df = pd.read_csv(CSV_PATH)
df['bar_time'] = pd.to_datetime(df['bar_time'], utc=True)
df = df.set_index('bar_time').sort_index()

# Prep indicators
df['funding_fresh'] = df['funding_rate'] != df['funding_rate'].shift(1)
df['roll_low_24'] = df['perp_close'].shift(1).rolling(24, min_periods=24).min()
df['volume_ma_20'] = df['perp_volume'].rolling(20).mean()

print("="*70)
print("QUICK IMPROVEMENT TEST - 3 Variations")
print("="*70)

# ============ DEFINE 4 STRATEGIES ============

def backtest_long_strategy(df, stop_pct, target_pct, use_volume_filter, strategy_name):
    """Run backtest with specific parameters"""
    
    trades = []
    open_longs = []
    last_long_entry_bar = -MIN_BARS_BETWEEN_ENTRIES
    
    for i in range(24, len(df)):
        # Entry signal
        funding_ok = df['funding_rate'].iloc[i] <= EXTREME_LOW_FUNDING
        price_ok = df['perp_close'].iloc[i] <= df['roll_low_24'].iloc[i] * (1 + PRICE_BUFFER_PCT)
        fresh_ok = df['funding_fresh'].iloc[i]
        throttle_ok = (i - last_long_entry_bar) >= MIN_BARS_BETWEEN_ENTRIES
        
        # Volume filter (optional)
        if use_volume_filter:
            volume_ok = df['perp_volume'].iloc[i] > df['volume_ma_20'].iloc[i]
        else:
            volume_ok = True
        
        # Enter LONG
        if funding_ok and price_ok and fresh_ok and throttle_ok and volume_ok:
            open_longs.append({
                'entry_bar': i,
                'entry_time': df.index[i],
                'entry_price': df['perp_close'].iloc[i]
            })
            last_long_entry_bar = i
        
        # Check exits for all open positions
        for pos_idx in range(len(open_longs) - 1, -1, -1):
            pos = open_longs[pos_idx]
            bars_held = i - pos['entry_bar']
            current_low = df['perp_low'].iloc[i]
            current_close = df['perp_close'].iloc[i]
            
            pnl_pct_stop = (current_low - pos['entry_price']) / pos['entry_price']
            pnl_pct_close = (current_close - pos['entry_price']) / pos['entry_price']
            
            exit_reason = None
            exit_price = None
            
            if pnl_pct_stop <= -stop_pct:
                exit_reason = 'stop_loss'
                exit_price = pos['entry_price'] * (1 - stop_pct)
            elif pnl_pct_close >= target_pct:
                exit_reason = 'profit_target'
                exit_price = current_close
            elif bars_held >= 42:
                exit_reason = 'time_limit'
                exit_price = current_close
            
            if exit_reason:
                pnl_before_fees = (exit_price - pos['entry_price']) / pos['entry_price'] * 100
                pnl_after_fees = pnl_before_fees - (TRADING_FEE_ROUND_TRIP * 100)
                
                trades.append({
                    'entry_time': pos['entry_time'],
                    'exit_time': df.index[i],
                    'entry_price': pos['entry_price'],
                    'exit_price': exit_price,
                    'bars_held': bars_held,
                    'pnl_pct': pnl_after_fees,
                    'exit_reason': exit_reason
                })
                del open_longs[pos_idx]
    
    # Close remaining positions
    for pos in open_longs:
        pnl_before_fees = (df['perp_close'].iloc[-1] - pos['entry_price']) / pos['entry_price'] * 100
        pnl_after_fees = pnl_before_fees - (TRADING_FEE_ROUND_TRIP * 100)
        trades.append({
            'entry_time': pos['entry_time'],
            'exit_time': df.index[-1],
            'entry_price': pos['entry_price'],
            'exit_price': df['perp_close'].iloc[-1],
            'bars_held': len(df) - 1 - pos['entry_bar'],
            'pnl_pct': pnl_after_fees,
            'exit_reason': 'end_of_data'
        })
    
    # Calculate metrics
    if len(trades) == 0:
        return None
    
    trades_df = pd.DataFrame(trades)
    winners = trades_df[trades_df['pnl_pct'] > 0]
    losers = trades_df[trades_df['pnl_pct'] <= 0]
    
    gp = winners['pnl_pct'].sum() if len(winners) > 0 else 0
    gl = abs(losers['pnl_pct'].sum()) if len(losers) > 0 else 0.001
    pf = gp / gl
    
    return {
        'name': strategy_name,
        'total_trades': len(trades_df),
        'win_rate': len(winners) / len(trades_df) * 100,
        'avg_pnl': trades_df['pnl_pct'].mean(),
        'total_pnl': trades_df['pnl_pct'].sum(),
        'profit_factor': pf,
        'stop_rate': (trades_df['exit_reason']=='stop_loss').sum() / len(trades_df) * 100,
        'avg_bars_held': trades_df['bars_held'].mean()
    }

# ============ RUN ALL 4 TESTS ============

print("\nRunning 4 strategy variations...\n")

results = []

# Baseline (your current LONG-only)
results.append(backtest_long_strategy(
    df, 
    stop_pct=0.03, 
    target_pct=0.04, 
    use_volume_filter=False,
    strategy_name="BASELINE (Current)"
))

# Test 1: Volume filter
results.append(backtest_long_strategy(
    df,
    stop_pct=0.03,
    target_pct=0.04,
    use_volume_filter=True,
    strategy_name="+ Volume Filter"
))

# Test 2: Wider stop
results.append(backtest_long_strategy(
    df,
    stop_pct=0.04,
    target_pct=0.04,
    use_volume_filter=False,
    strategy_name="+ Wider Stop (4%)"
))

# Test 3: Both improvements
results.append(backtest_long_strategy(
    df,
    stop_pct=0.04,
    target_pct=0.04,
    use_volume_filter=True,
    strategy_name="+ Both (Vol + 4% Stop)"
))

# ============ DISPLAY RESULTS ============

print("="*70)
print("RESULTS COMPARISON")
print("="*70)

results_df = pd.DataFrame([r for r in results if r is not None])
results_df = results_df.round(2)

print("\n" + results_df.to_string(index=False))

# Find best
best_pf = results_df.loc[results_df['profit_factor'].idxmax()]

print("\n" + "="*70)
print("🏆 WINNER")
print("="*70)
print(f"\nBest strategy: {best_pf['name']}")
print(f"Profit Factor: {best_pf['profit_factor']:.2f}")
print(f"Total Trades: {int(best_pf['total_trades'])}")
print(f"Win Rate: {best_pf['win_rate']:.1f}%")
print(f"Total PnL: {best_pf['total_pnl']:+.2f}%")

improvement = ((best_pf['profit_factor'] / results_df.iloc[0]['profit_factor']) - 1) * 100

print(f"\n📈 Improvement vs baseline: {improvement:+.1f}%")

if best_pf['profit_factor'] >= 1.6:
    print("\n✅ TARGET ACHIEVED! PF ≥ 1.6 - This is tradeable!")
elif best_pf['profit_factor'] >= 1.5:
    print("\n🟡 Close to target. One more tweak might get you there.")
else:
    print("\n⚠️  Still needs work, but you can see what direction to go.")

print("\n" + "="*70)
print("💡 INSIGHT")
print("="*70)

# Analyze what helped
vol_improvement = results_df[results_df['name']=='+ Volume Filter']['profit_factor'].values[0]
stop_improvement = results_df[results_df['name']=='+ Wider Stop (4%)']['profit_factor'].values[0]
baseline = results_df[results_df['name']=='BASELINE (Current)']['profit_factor'].values[0]

if vol_improvement > baseline and stop_improvement > baseline:
    print("\n✅ Both improvements help! Use the combined version.")
elif vol_improvement > stop_improvement:
    print("\n✅ Volume filter is the key! Stop size is fine.")
elif stop_improvement > vol_improvement:
    print("\n✅ Wider stop is the key! Volume filter doesn't matter.")
else:
    print("\n⚠️  Neither improvement helps much. Need different approach.")

print("\n" + "="*70)
print("🎯 NEXT STEPS")
print("="*70)

if best_pf['profit_factor'] >= 1.6:
    print("\n1. You're done! Use the winning strategy")
    print("2. Paper trade it for 1 month to build confidence")
    print("3. Then go live with conservative position sizing")
elif best_pf['profit_factor'] >= 1.5:
    print("\n1. Try one more tweak: 5% profit target instead of 4%")
    print("2. Or test tighter funding threshold (0.00002 instead of 0.00003)")
else:
    print("\n1. Accept current strategy might need different approach")
    print("2. Consider testing on different timeframe (8H bars?)")
    print("3. Or just trade current version conservatively")

print("\n" + "="*70)
print("⏱️  Total time elapsed: ~5 minutes")
print("="*70)
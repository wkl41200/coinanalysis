import pandas as pd
import numpy as np

"""
PROFIT TARGET OPTIMIZATION
Test: Does increasing profit target improve PF without filtering trades?
Time: 2 minutes
"""

CSV_PATH = 'BTC_perp_funding_combined_OHLC.csv'

df = pd.read_csv(CSV_PATH)
df['bar_time'] = pd.to_datetime(df['bar_time'], utc=True)
df = df.set_index('bar_time').sort_index()

df['funding_fresh'] = df['funding_rate'] != df['funding_rate'].shift(1)
df['roll_low_24'] = df['perp_close'].shift(1).rolling(24, min_periods=24).min()

EXTREME_LOW_FUNDING = 0.00003
PRICE_BUFFER_PCT = 0.03
MIN_BARS_BETWEEN_ENTRIES = 6
STOP_LOSS = 0.03
TAKER_FEE = 0.0004
TRADING_FEE_ROUND_TRIP = TAKER_FEE * 2

def test_profit_target(target_pct):
    """Quick backtest with different profit targets"""
    trades = []
    open_longs = []
    last_entry = -MIN_BARS_BETWEEN_ENTRIES
    
    for i in range(24, len(df)):
        # Entry (no filters, keep all trades)
        if (df['funding_rate'].iloc[i] <= EXTREME_LOW_FUNDING and
            df['perp_close'].iloc[i] <= df['roll_low_24'].iloc[i] * (1 + PRICE_BUFFER_PCT) and
            df['funding_fresh'].iloc[i] and
            (i - last_entry) >= MIN_BARS_BETWEEN_ENTRIES):
            
            open_longs.append({
                'entry_bar': i,
                'entry_time': df.index[i],
                'entry_price': df['perp_close'].iloc[i]
            })
            last_entry = i
        
        # Exits
        for pos_idx in range(len(open_longs) - 1, -1, -1):
            pos = open_longs[pos_idx]
            bars_held = i - pos['entry_bar']
            
            pnl_stop = (df['perp_low'].iloc[i] - pos['entry_price']) / pos['entry_price']
            pnl_close = (df['perp_close'].iloc[i] - pos['entry_price']) / pos['entry_price']
            
            exit_reason = None
            exit_price = None
            
            if pnl_stop <= -STOP_LOSS:
                exit_reason = 'stop'
                exit_price = pos['entry_price'] * (1 - STOP_LOSS)
            elif pnl_close >= target_pct:
                exit_reason = 'target'
                exit_price = df['perp_close'].iloc[i]
            elif bars_held >= 42:
                exit_reason = 'time'
                exit_price = df['perp_close'].iloc[i]
            
            if exit_reason:
                pnl = ((exit_price - pos['entry_price']) / pos['entry_price'] * 100) - (TRADING_FEE_ROUND_TRIP * 100)
                trades.append({'pnl_pct': pnl, 'exit_reason': exit_reason})
                del open_longs[pos_idx]
    
    # Close remaining
    for pos in open_longs:
        pnl = ((df['perp_close'].iloc[-1] - pos['entry_price']) / pos['entry_price'] * 100) - (TRADING_FEE_ROUND_TRIP * 100)
        trades.append({'pnl_pct': pnl, 'exit_reason': 'eod'})
    
    if len(trades) == 0:
        return None
    
    trades_df = pd.DataFrame(trades)
    winners = trades_df[trades_df['pnl_pct'] > 0]
    losers = trades_df[trades_df['pnl_pct'] <= 0]
    
    gp = winners['pnl_pct'].sum() if len(winners) > 0 else 0
    gl = abs(losers['pnl_pct'].sum()) if len(losers) > 0 else 0.001
    
    return {
        'target': f"{target_pct*100:.1f}%",
        'trades': len(trades_df),
        'win_rate': len(winners)/len(trades_df)*100,
        'pf': gp/gl,
        'total_pnl': trades_df['pnl_pct'].sum(),
        'avg_pnl': trades_df['pnl_pct'].mean(),
        'target_exits': (trades_df['exit_reason']=='target').sum() / len(trades_df) * 100
    }

print("="*70)
print("PROFIT TARGET OPTIMIZATION")
print("="*70)

print("\nTesting profit targets from 4% to 12%...")
print("(Keeping ALL 71 trades, no filtering)\n")

results = []
for target in [0.04, 0.045, 0.05, 0.055, 0.06, 0.065, 0.07, 0.075, 0.08, 0.09, 0.1, 0.11, 0.12, 0.125, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18, 0.19, 0.2]:
    result = test_profit_target(target)
    if result:
        results.append(result)

results_df = pd.DataFrame(results)
print(results_df.to_string(index=False))

# Find sweet spot
best = results_df.loc[results_df['pf'].idxmax()]

print("\n" + "="*70)
print("🎯 OPTIMAL TARGET")
print("="*70)
print(f"\nBest profit target: {best['target']}")
print(f"Profit Factor: {best['pf']:.2f}")
print(f"Win Rate: {best['win_rate']:.1f}%")
print(f"Total PnL: {best['total_pnl']:+.2f}%")
print(f"Total Trades: {int(best['trades'])}")

improvement = ((best['pf'] / results_df.iloc[0]['pf']) - 1) * 100
print(f"\n📈 Improvement vs 4% target: {improvement:+.1f}%")

if best['pf'] >= 1.6:
    print("\n✅ TARGET ACHIEVED! PF ≥ 1.6")
    print("   → This is tradeable!")
    print("   → No filtering needed, just better exits")
elif best['pf'] >= 1.55:
    print("\n🟢 Very close! PF ≥ 1.55")
    print("   → One more small tweak and you're there")
else:
    print("\n🟡 Improved but not quite there")
    print("   → May need filtering after all")

print("\n" + "="*70)
print("💡 INSIGHT")
print("="*70)

if best['target'] == '4.0%':
    print("\n⚠️  Original 4% target is already optimal")
    print("   → Need to filter entries, not adjust exits")
else:
    print(f"\n✅ Increasing target to {best['target']} helps!")
    print("   → Let winners run = higher PF")
    print("   → Keep all trades = maximize profit")
    
print(f"\nTrade-off at {best['target']}:")
print(f"  - Hit target: {best['target_exits']:.0f}% of trades")
print(f"  - Win rate: {best['win_rate']:.1f}%")
print(f"  - Fewer quick wins, but bigger wins when they hit")

print("\n" + "="*70)
print("🚀 NEXT STEP")
print("="*70)

if best['pf'] >= 1.6:
    print("\n✅ USE THIS STRATEGY AS-IS")
    print(f"   - Profit target: {best['target']}")
    print("   - No entry filters needed")
    print("   - Start paper trading!")
elif best['pf'] >= 1.55:
    print("\n🔧 ALMOST THERE - Try ONE more thing:")
    print("   Option A: Test trailing stop instead of fixed target")
    print("   Option B: Combine with looser volume filter (>0.8x)")
else:
    print("\n⚠️  Exit optimization alone isn't enough")
    print("   → Need better entry filtering")
    print("   → Run the funding extremeness test next")

print("\n" + "="*70)
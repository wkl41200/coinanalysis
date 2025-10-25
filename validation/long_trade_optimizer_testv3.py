import pandas as pd
import numpy as np

"""
LONG TRADE OPTIMIZATION ANALYSIS
Purpose: Understand what makes LONG trades succeed or fail
This guides us on what to optimize (entries vs exits)
"""

# ============ LOAD DATA ============
trades = pd.read_csv('/Users/duncanwan/Desktop/learning/Bitcoin/simple_strategy_trades.csv')
trades['entry_time'] = pd.to_datetime(trades['entry_time'])
trades['exit_time'] = pd.to_datetime(trades['exit_time'])

# Filter for LONG trades only
longs = trades[trades['side'] == 'LONG'].copy()

print("="*70)
print("LONG TRADE OPTIMIZATION ANALYSIS")
print("="*70)

print(f"\nTotal LONG trades: {len(longs)}")
print(f"Current Profit Factor: 1.48")
print(f"Current Win Rate: 49.3%")
print("\n🎯 GOAL: Improve to PF 1.8+ before considering position sizing")

# ============ 1. STOP LOSS ANALYSIS ============
print("\n" + "="*70)
print("1. STOP LOSS ANALYSIS - Are stops too tight?")
print("="*70)

stops = longs[longs['exit_reason'] == 'stop_loss']
print(f"\nStop losses hit: {len(stops)} / {len(longs)} ({len(stops)/len(longs)*100:.1f}%)")
print(f"Average bars before stop: {stops['bars_held'].mean():.1f}")
print(f"Median bars before stop: {stops['bars_held'].median():.0f}")

quick_stops = stops[stops['bars_held'] <= 3]  # Stopped out within 12 hours
print(f"\nQuick stops (≤3 bars): {len(quick_stops)} ({len(quick_stops)/len(stops)*100:.1f}% of stops)")

if len(quick_stops) > len(stops) * 0.3:
    print("❌ PROBLEM: >30% stops hit quickly = Bad entries or stops too tight")
    print("   Recommendation: Either improve entry filter OR widen stop to 4%")
else:
    print("✅ Stops hit gradually = Trend continuation, not bad entries")
    print("   Recommendation: Keep 3% stop, focus on entry filter")

# ============ 2. PROFIT TARGET ANALYSIS ============
print("\n" + "="*70)
print("2. PROFIT TARGET ANALYSIS - Are we exiting too early?")
print("="*70)

targets = longs[longs['exit_reason'] == 'profit_target']
print(f"\nProfit targets hit: {len(targets)} / {len(longs)} ({len(targets)/len(longs)*100:.1f}%)")
print(f"Average bars to target: {targets['bars_held'].mean():.1f}")
print(f"Average PnL at target: {targets['pnl_pct'].mean():+.2f}%")

# Load price data to check if we could have held longer
df = pd.read_csv('BTC_perp_funding_combined_OHLC.csv')
df['bar_time'] = pd.to_datetime(df['bar_time'], utc=True)
df = df.set_index('bar_time').sort_index()

# Check if price continued higher after we exited
targets['price_5bars_later'] = targets['exit_time'].map(
    lambda t: df.loc[df.index > t].head(5)['perp_close'].max() if t in df.index and len(df.loc[df.index > t]) >= 5 else np.nan
)
targets['could_have_made'] = ((targets['price_5bars_later'] - targets['entry_price']) / targets['entry_price'] * 100) - 0.08

profitable_continuation = targets[targets['could_have_made'] > targets['pnl_pct']]
print(f"\nTrades that continued higher: {len(profitable_continuation)} / {len(targets)} ({len(profitable_continuation)/len(targets)*100:.1f}%)")

if len(profitable_continuation) > len(targets) * 0.5:
    print("❌ PROBLEM: >50% trades continued higher after exit")
    print("   Recommendation: Increase target to 5-6% OR use trailing stop")
else:
    print("✅ Taking profit at 4% is reasonable")
    print("   Recommendation: Keep current target")

# ============ 3. ENTRY TIMING ANALYSIS ============
print("\n" + "="*70)
print("3. ENTRY TIMING - What makes entries succeed?")
print("="*70)

winners = longs[longs['pnl_pct'] > 0]
losers = longs[longs['pnl_pct'] <= 0]

print(f"\nWinners: {len(winners)}")
print(f"  Avg entry funding: {winners['entry_funding'].mean():.6f}")
print(f"  Avg bars held: {winners['bars_held'].mean():.1f}")

print(f"\nLosers: {len(losers)}")
print(f"  Avg entry funding: {losers['entry_funding'].mean():.6f}")
print(f"  Avg bars held: {losers['bars_held'].mean():.1f}")

funding_diff = winners['entry_funding'].mean() - losers['entry_funding'].mean()
print(f"\nFunding difference: {funding_diff:.6f}")

if abs(funding_diff) > 0.00002:
    print("✅ Entry funding matters! Winners have different funding than losers")
    print("   Recommendation: Tighten funding threshold")
else:
    print("⚠️  Entry funding similar for winners/losers")
    print("   Recommendation: Funding threshold might not be the key filter")

# ============ 4. BEST vs WORST TRADES ============
print("\n" + "="*70)
print("4. COMPARING BEST vs WORST TRADES")
print("="*70)

best5 = longs.nlargest(5, 'pnl_pct')
worst5 = longs.nsmallest(5, 'pnl_pct')

print("\n🟢 TOP 5 BEST LONG TRADES:")
cols = ['entry_time', 'entry_price', 'entry_funding', 'bars_held', 'pnl_pct', 'exit_reason']
print(best5[cols].to_string(index=False))

print("\n🔴 TOP 5 WORST LONG TRADES:")
print(worst5[cols].to_string(index=False))

print("\nLook for patterns:")
print("- Do best trades have more extreme funding?")
print("- Do worst trades enter during specific market conditions?")
print("- Is there a holding period sweet spot?")

# ============ 5. TIME DECAY ANALYSIS ============
print("\n" + "="*70)
print("5. TIME DECAY - Does holding longer help or hurt?")
print("="*70)

# Group by holding period
longs['hold_bucket'] = pd.cut(longs['bars_held'], bins=[0, 5, 10, 20, 50], labels=['0-5', '6-10', '11-20', '21+'])
hold_analysis = longs.groupby('hold_bucket').agg({
    'pnl_pct': ['count', 'mean', 'sum'],
    'exit_reason': lambda x: (x=='stop_loss').sum() / len(x) * 100
})
hold_analysis.columns = ['Count', 'Avg_PnL', 'Total_PnL', 'Stop_%']

print("\nPerformance by holding period:")
print(hold_analysis.to_string())

best_bucket = hold_analysis['Avg_PnL'].idxmax()
print(f"\n✅ Sweet spot: {best_bucket} bars")
print("   Recommendation: Consider adding time-based exit at this range")

# ============ 6. OPTIMIZATION ROADMAP ============
print("\n" + "="*70)
print("🗺️  OPTIMIZATION ROADMAP")
print("="*70)

print("\nBased on analysis above, here's what to test IN ORDER:")

# Calculate potential impact
stop_improvement = len(quick_stops) * 3.08  # If we avoid quick stops
target_improvement = len(profitable_continuation) * 2.0 if len(targets) > 0 else 0  # If we hold longer

print(f"\n1. ENTRY FILTER IMPROVEMENT (Highest Priority)")
print(f"   Potential gain: ~{stop_improvement:.1f}% (avoid quick stop-outs)")
print(f"   Action: Add volume filter, or tighter funding threshold")
print(f"   Expected new PF: 1.6-1.7")

print(f"\n2. EXIT OPTIMIZATION (Medium Priority)")
print(f"   Potential gain: ~{target_improvement:.1f}% (hold winners longer)")
print(f"   Action: Test 5% target or trailing stop")
print(f"   Expected new PF: 1.7-1.8")

print(f"\n3. STOP LOSS ADJUSTMENT (Low Priority)")
print(f"   Potential impact: ±5-10%")
print(f"   Action: Test 2.5% (tighter) vs 4% (wider)")
print(f"   Expected new PF: 1.5-1.6")

print(f"\n4. POSITION SIZING (LAST - Do This Only After PF > 1.6)")
print(f"   Current: Fixed $10k per trade")
print(f"   Future: Kelly Criterion or Fixed % risk")
print(f"   With 2x leverage: Could double returns (but also double risk)")

# ============ 7. WHAT NOT TO DO ============
print("\n" + "="*70)
print("⚠️  WHAT NOT TO DO")
print("="*70)

print("\n❌ DON'T use 50x leverage")
print("   - One 3% loss = 150% account wipe")
print("   - Even pros use max 5-10x")

print("\n❌ DON'T 'double down' on losers (Martingale)")
print("   - Guaranteed eventual ruin")
print("   - Turns small losses into catastrophes")

print("\n❌ DON'T optimize position sizing before entries/exits")
print("   - Sizing multiplies edge - need edge first")
print("   - Without PF > 1.5, aggressive sizing = faster losses")

print("\n❌ DON'T test position sizing on same data you optimized on")
print("   - Need fresh data for walk-forward testing")
print("   - Or at minimum, split data 70/30 train/test")

print("\n" + "="*70)
print("NEXT STEP: Pick ONE thing to improve from the roadmap above")
print("="*70)
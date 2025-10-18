import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

"""
TRADE DIAGNOSTICS - Deep Dive Analysis
Purpose: Understand WHY the strategy isn't working before tweaking parameters
"""

# ============ LOAD TRADES ============
trades_df = pd.read_csv('simple_strategy_trades.csv')
trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time'])
trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'])
trades_df['month'] = trades_df['entry_time'].dt.to_period('M')

print("="*70)
print("DIAGNOSTIC ANALYSIS - Understanding Your Results")
print("="*70)

# ============ 1. SHORT vs LONG PERFORMANCE ============
print("\n" + "="*70)
print("1. SHORT vs LONG PERFORMANCE")
print("="*70)

for side in ['SHORT', 'LONG']:
    subset = trades_df[trades_df['side'] == side]
    if len(subset) == 0:
        continue
    
    winners = subset[subset['pnl_pct'] > 0]
    losers = subset[subset['pnl_pct'] <= 0]
    
    print(f"\n{side}:")
    print(f"  Total trades: {len(subset)}")
    print(f"  Win rate: {len(winners)/len(subset)*100:.1f}%")
    print(f"  Average PnL: {subset['pnl_pct'].mean():+.2f}%")
    print(f"  Total PnL: {subset['pnl_pct'].sum():+.2f}%")
    
    # Profit factor
    gp = winners['pnl_pct'].sum() if len(winners) > 0 else 0
    gl = abs(losers['pnl_pct'].sum()) if len(losers) > 0 else 0
    pf = gp / gl if gl > 0 else np.inf
    print(f"  Profit Factor: {pf:.2f}")
    
    # Exit breakdown
    print(f"  Exit breakdown:")
    for reason in ['stop_loss', 'profit_target', 'time_limit']:
        count = len(subset[subset['exit_reason'] == reason])
        if count > 0:
            pct = count / len(subset) * 100
            avg = subset[subset['exit_reason'] == reason]['pnl_pct'].mean()
            print(f"    {reason:15s}: {count:3d} ({pct:4.1f}%) | Avg: {avg:+.2f}%")

# ============ 2. MONTHLY BREAKDOWN ============
print("\n" + "="*70)
print("2. MONTHLY PERFORMANCE (Regime Analysis)")
print("="*70)

monthly = trades_df.groupby('month').agg({
    'pnl_pct': ['count', 'sum', 'mean'],
    'side': lambda x: f"{(x=='SHORT').sum()}S/{(x=='LONG').sum()}L"
})
monthly.columns = ['Trades', 'Total_PnL', 'Avg_PnL', 'S/L']

print("\nMonthly breakdown:")
print(monthly.to_string())

# Identify worst months
worst_months = monthly.nsmallest(3, 'Total_PnL')
print("\n🔴 WORST 3 MONTHS:")
print(worst_months[['Trades', 'Total_PnL', 'Avg_PnL', 'S/L']].to_string())

best_months = monthly.nlargest(3, 'Total_PnL')
print("\n🟢 BEST 3 MONTHS:")
print(best_months[['Trades', 'Total_PnL', 'Avg_PnL', 'S/L']].to_string())

# ============ 3. CONSECUTIVE LOSERS (Trade Clustering) ============
print("\n" + "="*70)
print("3. TRADE CLUSTERING (Consecutive Losses)")
print("="*70)

# Identify consecutive losses
trades_df['is_loser'] = trades_df['pnl_pct'] <= 0
trades_df['loss_streak'] = (trades_df['is_loser'] != trades_df['is_loser'].shift()).cumsum()
loss_streaks = trades_df[trades_df['is_loser']].groupby('loss_streak').size()

max_streak = loss_streaks.max() if len(loss_streaks) > 0 else 0
print(f"\nLongest losing streak: {max_streak} trades")
print(f"Number of losing streaks ≥3: {(loss_streaks >= 3).sum()}")

# Show example of a bad streak
if max_streak >= 5:
    worst_streak_id = loss_streaks.idxmax()
    worst_streak = trades_df[trades_df['loss_streak'] == worst_streak_id]
    print(f"\n🔴 Example of worst streak ({len(worst_streak)} consecutive losses):")
    cols = ['entry_time', 'side', 'entry_price', 'exit_price', 'pnl_pct', 'exit_reason']
    print(worst_streak[cols].to_string(index=False))

# ============ 4. ENTRY TIMING ISSUES ============
print("\n" + "="*70)
print("4. STOP LOSS ANALYSIS (Are stops too tight?)")
print("="*70)

stops = trades_df[trades_df['exit_reason'] == 'stop_loss']
print(f"\nTotal stop losses: {len(stops)} ({len(stops)/len(trades_df)*100:.1f}%)")
print(f"Average bars held before stop: {stops['bars_held'].mean():.1f}")
print(f"Median bars held before stop: {stops['bars_held'].median():.0f}")

# Check if stops hit quickly (bad entries) or slowly (trend continuation)
quick_stops = stops[stops['bars_held'] <= 5]
print(f"\nQuick stops (≤5 bars): {len(quick_stops)} ({len(quick_stops)/len(stops)*100:.1f}% of stops)")
print(f"  → Suggests: {'BAD ENTRIES' if len(quick_stops)/len(stops) > 0.5 else 'Trend continuation'}")

# ============ 5. PROFIT TARGET ANALYSIS ============
print("\n" + "="*70)
print("5. PROFIT TARGET ANALYSIS (Are winners held long enough?)")
print("="*70)

targets = trades_df[trades_df['exit_reason'] == 'profit_target']
print(f"\nProfit targets hit: {len(targets)} ({len(targets)/len(trades_df)*100:.1f}%)")
print(f"Average bars held for winners: {targets['bars_held'].mean():.1f}")
print(f"Average PnL on winners: {targets['pnl_pct'].mean():+.2f}%")

# ============ 6. KEY INSIGHTS ============
print("\n" + "="*70)
print("6. KEY INSIGHTS & RECOMMENDATIONS")
print("="*70)

# Calculate key ratios
short_pf = trades_df[trades_df['side']=='SHORT']['pnl_pct'].sum()
long_pf = trades_df[trades_df['side']=='LONG']['pnl_pct'].sum()
stop_rate = len(stops) / len(trades_df)

print("\n🔍 What the data is telling us:\n")

# Insight 1: Side bias
if abs(short_pf) < abs(long_pf) * 0.5:
    print("❌ SHORT PROBLEM:")
    print("   SHORTs are significantly underperforming LONGs")
    print("   → You might be shorting during a bull market")
    print("   → Consider: Only trade LONGs, or add trend filter\n")
elif abs(long_pf) < abs(short_pf) * 0.5:
    print("❌ LONG PROBLEM:")
    print("   LONGs are significantly underperforming SHORTs")
    print("   → You might be buying during a bear market")
    print("   → Consider: Only trade SHORTs, or add trend filter\n")

# Insight 2: Stop rate
if stop_rate > 0.55:
    print("❌ HIGH STOP RATE (>55%):")
    print("   More than half your trades hit stops")
    if quick_stops['bars_held'].mean() < 10:
        print("   → Stops hit QUICKLY = Bad entries or fighting trend")
        print("   → Consider: Tighter entry filter or add trend confirmation\n")
    else:
        print("   → Stops hit SLOWLY = Trend continuation against you")
        print("   → Consider: Wider stops or add trend filter\n")

# Insight 3: Median vs Average
if trades_df['pnl_pct'].median() < -2:
    print("❌ LOTTERY TICKET DISTRIBUTION:")
    print("   Median PnL is very negative but average is positive")
    print("   → Most trades lose, few big winners carry the strategy")
    print("   → This is HIGH RISK and unsustainable")
    print("   → Consider: Tighten entry filters to reduce losers\n")

# Insight 4: Sample size by side
short_count = len(trades_df[trades_df['side']=='SHORT'])
long_count = len(trades_df[trades_df['side']=='LONG'])
if abs(short_count - long_count) > 30:
    print("⚠️  IMBALANCED SIGNALS:")
    print(f"   {short_count} SHORTs vs {long_count} LONGs")
    print("   → One side is triggering much more often")
    print("   → This might indicate a directional bias in your data period\n")

# ============ 7. NEXT STEPS ============
print("="*70)
print("🎯 RECOMMENDED NEXT STEPS:")
print("="*70)
print("\nOption A: Add Trend Filter")
print("  - Only SHORT when price < 50-day MA")
print("  - Only LONG when price > 50-day MA")
print("  - This prevents fighting the trend\n")

print("Option B: Trade Only One Side")
print("  - If SHORTs are terrible, only trade LONGs")
print("  - If LONGs are terrible, only trade SHORTs\n")

print("Option C: Widen Stops")
print("  - Current: 3% stop loss")
print("  - Try: 4% or 5% to reduce stop-outs")
print("  - BUT: This increases risk per trade\n")

print("Option D: Tighten Entry Filter")
print("  - Increase price buffer from 3% to 2%")
print("  - Or require stronger funding extreme")
print("  - Trade less but with better entries\n")

print("="*70)
print("💡 MY RECOMMENDATION:")
print("="*70)
print("Based on your results, I suggest:")
print("1. First, add a TREND FILTER (Option A)")
print("2. Re-run the backtest and compare")
print("3. If still poor, try trading only the better-performing side")
print("\nDo you want me to add a trend filter to the code?")
print("="*70)
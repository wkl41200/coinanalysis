import pandas as pd
import numpy as np

"""
BIG LOSER ANALYSIS
Question: What causes the big losing trades?
Goal: Find the ONE filter that prevents disasters without cutting winners
"""

# ============ LOAD EXISTING TRADES ============
trades = pd.read_csv('simple_strategy_trades.csv')
trades['entry_time'] = pd.to_datetime(trades['entry_time'])
trades['exit_time'] = pd.to_datetime(trades['exit_time'])

# Filter for LONGs only
longs = trades[trades['side'] == 'LONG'].copy()

# Load price data for context
df = pd.read_csv('BTC_perp_funding_combined_OHLC.csv')
df['bar_time'] = pd.to_datetime(df['bar_time'], utc=True)
df = df.set_index('bar_time').sort_index()

# Add volume ratio
df['volume_ma_20'] = df['perp_volume'].rolling(20).mean()
df['volume_ratio'] = df['perp_volume'] / df['volume_ma_20']

# Map volume ratio to trades
longs['volume_ratio'] = longs['entry_time'].map(
    lambda t: df.loc[t, 'volume_ratio'] if t in df.index else np.nan
)

print("="*70)
print("BIG LOSER ANALYSIS - Finding the Root Cause")
print("="*70)

print(f"\nTotal LONG trades: {len(longs)}")
print(f"Current best: PF 1.58 with 4.5% target")

# ============ 1. IDENTIFY BIG LOSERS ============
print("\n" + "="*70)
print("1. WHO ARE THE BIG LOSERS?")
print("="*70)

losers = longs[longs['pnl_pct'] < -2.5]  # Worse than -2.5%
small_losers = longs[(longs['pnl_pct'] < 0) & (longs['pnl_pct'] >= -2.5)]
winners = longs[longs['pnl_pct'] > 0]

print(f"\nBig losers (<-2.5%): {len(losers)} trades")
print(f"  Total damage: {losers['pnl_pct'].sum():.2f}%")
print(f"  Average loss: {losers['pnl_pct'].mean():.2f}%")

print(f"\nSmall losers (-2.5% to 0%): {len(small_losers)} trades")
print(f"  Total damage: {small_losers['pnl_pct'].sum():.2f}%")

print(f"\nWinners: {len(winners)} trades")
print(f"  Total profit: {winners['pnl_pct'].sum():.2f}%")

print(f"\n💡 KEY INSIGHT:")
big_loser_impact = abs(losers['pnl_pct'].sum())
total_loss = abs(longs[longs['pnl_pct'] < 0]['pnl_pct'].sum())
print(f"   Big losers cause {big_loser_impact/total_loss*100:.1f}% of all losses")
print(f"   If we could filter these out → Major PF improvement!")

# ============ 2. BIG LOSER CHARACTERISTICS ============
print("\n" + "="*70)
print("2. WHAT DO BIG LOSERS HAVE IN COMMON?")
print("="*70)

print("\n📊 EXIT REASONS:")
for reason in ['stop_loss', 'time_limit']:
    big_count = len(losers[losers['exit_reason'] == reason])
    small_count = len(small_losers[small_losers['exit_reason'] == reason])
    winner_count = len(winners[winners['exit_reason'] == reason])
    
    print(f"  {reason:15s}: Big losers={big_count}, Small losers={small_count}, Winners={winner_count}")

print("\n📊 VOLUME AT ENTRY:")
print(f"  Big losers avg volume ratio: {losers['volume_ratio'].mean():.2f}x")
print(f"  Small losers avg volume ratio: {small_losers['volume_ratio'].mean():.2f}x")
print(f"  Winners avg volume ratio: {winners['volume_ratio'].mean():.2f}x")

volume_helps = winners['volume_ratio'].mean() - losers['volume_ratio'].mean()
if volume_helps > 0.2:
    print(f"  ✅ Volume difference: {volume_helps:.2f}x (significant!)")
else:
    print(f"  ⚠️  Volume difference: {volume_helps:.2f}x (minimal)")

print("\n📊 HOLDING PERIOD:")
print(f"  Big losers avg bars held: {losers['bars_held'].mean():.1f}")
print(f"  Small losers avg bars held: {small_losers['bars_held'].mean():.1f}")
print(f"  Winners avg bars held: {winners['bars_held'].mean():.1f}")

print("\n📊 FUNDING AT ENTRY:")
print(f"  Big losers avg funding: {losers['entry_funding'].mean():.6f}")
print(f"  Small losers avg funding: {small_losers['entry_funding'].mean():.6f}")
print(f"  Winners avg funding: {winners['entry_funding'].mean():.6f}")

# ============ 3. SHOW ACTUAL BIG LOSERS ============
print("\n" + "="*70)
print("3. THE ACTUAL BIG LOSING TRADES")
print("="*70)

worst_trades = longs.nsmallest(10, 'pnl_pct')
cols = ['entry_time', 'entry_price', 'entry_funding', 'volume_ratio', 'bars_held', 'pnl_pct', 'exit_reason']
print("\nWorst 10 trades:")
print(worst_trades[cols].to_string(index=False))

# ============ 4. TEST FILTERS ============
print("\n" + "="*70)
print("4. TESTING FILTERS TO AVOID BIG LOSERS")
print("="*70)

def test_filter(trades_df, filter_name, filter_func):
    """Test if a filter would have removed big losers"""
    kept = trades_df[filter_func(trades_df)]
    removed = trades_df[~filter_func(trades_df)]
    
    kept_big_losers = len(kept[kept['pnl_pct'] < -2.5])
    removed_big_losers = len(removed[removed['pnl_pct'] < -2.5])
    
    kept_winners = len(kept[kept['pnl_pct'] > 0])
    removed_winners = len(removed[removed['pnl_pct'] > 0])
    
    print(f"\n{filter_name}:")
    print(f"  Keeps: {len(kept)} trades | Removes: {len(removed)} trades")
    print(f"  Big losers removed: {removed_big_losers}/{len(losers)} ({removed_big_losers/len(losers)*100:.0f}%)")
    print(f"  Winners kept: {kept_winners}/{len(winners)} ({kept_winners/len(winners)*100:.0f}%)")
    
    if len(kept) > 0:
        kept_winners_df = kept[kept['pnl_pct'] > 0]
        kept_losers_df = kept[kept['pnl_pct'] <= 0]
        gp = kept_winners_df['pnl_pct'].sum() if len(kept_winners_df) > 0 else 0
        gl = abs(kept_losers_df['pnl_pct'].sum()) if len(kept_losers_df) > 0 else 0.001
        new_pf = gp / gl
        print(f"  New PF: {new_pf:.2f} (was 1.58)")
        print(f"  New Total PnL: {kept['pnl_pct'].sum():+.2f}% (was +64.57%)")
        return new_pf
    return 0

# Filter 1: Volume > 1.0x
pf1 = test_filter(longs, "FILTER 1: Volume > 1.0x avg", 
                  lambda df: df['volume_ratio'] > 1.0)

# Filter 2: Volume > 0.8x (looser)
pf2 = test_filter(longs, "FILTER 2: Volume > 0.8x avg",
                  lambda df: df['volume_ratio'] > 0.8)

# Filter 3: Extreme funding (<= 0.00002)
pf3 = test_filter(longs, "FILTER 3: Funding ≤ 0.00002",
                  lambda df: df['entry_funding'] <= 0.00002)

# Filter 4: Volume > 0.8x AND Funding <= 0.000025
pf4 = test_filter(longs, "FILTER 4: Vol>0.8x AND Fund≤0.000025",
                  lambda df: (df['volume_ratio'] > 0.8) & (df['entry_funding'] <= 0.000025))

# ============ 5. RECOMMENDATION ============
print("\n" + "="*70)
print("🎯 FINAL RECOMMENDATION")
print("="*70)

filters_tested = [
    ("No filter", 1.58, 71, 64.57),
    ("Volume > 1.0x", pf1, len(longs[longs['volume_ratio'] > 1.0]), longs[longs['volume_ratio'] > 1.0]['pnl_pct'].sum()),
    ("Volume > 0.8x", pf2, len(longs[longs['volume_ratio'] > 0.8]), longs[longs['volume_ratio'] > 0.8]['pnl_pct'].sum()),
    ("Funding ≤ 0.00002", pf3, len(longs[longs['entry_funding'] <= 0.00002]), longs[longs['entry_funding'] <= 0.00002]['pnl_pct'].sum()),
    ("Combined", pf4, len(longs[(longs['volume_ratio'] > 0.8) & (longs['entry_funding'] <= 0.000025)]), 
     longs[(longs['volume_ratio'] > 0.8) & (longs['entry_funding'] <= 0.000025)]['pnl_pct'].sum())
]

print("\nComparison:")
for name, pf, trades, total_pnl in filters_tested:
    print(f"  {name:20s}: PF {pf:.2f} | {trades} trades | Total {total_pnl:+.1f}%")

best_pf = max(filters_tested, key=lambda x: x[1])
best_profit = max(filters_tested, key=lambda x: x[3])

print(f"\n🏆 Best PF: {best_pf[0]} (PF {best_pf[1]:.2f})")
print(f"💰 Best Total Profit: {best_profit[0]} ({best_profit[3]:+.1f}%)")

print("\n" + "="*70)
print("💡 FINAL DECISION")
print("="*70)

if best_pf[1] >= 1.6 and best_pf[2] >= 40:
    print(f"\n✅ USE: {best_pf[0]}")
    print(f"   PF: {best_pf[1]:.2f} (target achieved!)")
    print(f"   Trades: {best_pf[2]} (sufficient sample)")
    print(f"   Total: {best_pf[3]:+.1f}%")
    print("\n   🎉 STRATEGY IS READY TO TRADE!")
elif best_pf[1] >= 1.55:
    print(f"\n🟢 ALMOST THERE with: {best_pf[0]}")
    print(f"   PF: {best_pf[1]:.2f} (close to 1.6 target)")
    print(f"   This is tradeable, but could try one more tweak")
else:
    print(f"\n🟡 NO FILTER NEEDED")
    print(f"   Filtering reduces profit more than it improves PF")
    print(f"   Trade the unfiltered version (PF 1.58, +64.57%)")
    print(f"   Accept that some trades will lose - that's normal")

print("\n" + "="*70)
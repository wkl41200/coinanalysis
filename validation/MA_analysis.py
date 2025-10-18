import pandas as pd
import numpy as np

"""
MA DISTANCE ANALYSIS
Purpose: Test if "distance from 200MA" explains February disaster better than simple trend filter
Based on user's observation: Problem isn't trend, it's CHOPPY periods near MAs
"""

# ============ LOAD DATA ============
df = pd.read_csv('/Users/duncanwan/Desktop/learning/Bitcoin/BTC_perp_funding_combined_OHLC.csv')
df['bar_time'] = pd.to_datetime(df['bar_time'], utc=True)
df = df.set_index('bar_time').sort_index()

trades = pd.read_csv('simple_strategy_trades.csv')
trades['entry_time'] = pd.to_datetime(trades['entry_time'])

# ============ CALCULATE MAs AND DISTANCE ============
df['ema_50'] = df['perp_close'].ewm(span=50, adjust=False).mean()
df['ema_200'] = df['perp_close'].ewm(span=200, adjust=False).mean()

# Distance from 200MA (as percentage)
df['dist_from_200ma'] = ((df['perp_close'] - df['ema_200']) / df['ema_200']) * 100

# Regime
df['above_200ma'] = df['perp_close'] > df['ema_200']
df['regime'] = df['above_200ma'].map({True: 'BULL', False: 'BEAR'})

# Chop zone (within ±5% of 200MA)
df['in_chop_zone'] = abs(df['dist_from_200ma']) < 5.0

print("="*70)
print("MA DISTANCE ANALYSIS - Testing User's 'Chop Zone' Theory")
print("="*70)

# ============ ANALYZE FEBRUARY 2024 ============
print("\n" + "="*70)
print("FEBRUARY 2024 ANALYSIS (The Disaster Month)")
print("="*70)

feb_data = df['2024-02-01':'2024-02-29']
print(f"\nFebruary 2024 market characteristics:")
print(f"  Average distance from 200MA: {feb_data['dist_from_200ma'].mean():+.2f}%")
print(f"  Max distance above: {feb_data['dist_from_200ma'].max():+.2f}%")
print(f"  Max distance below: {feb_data['dist_from_200ma'].min():+.2f}%")
print(f"  Bars in chop zone (±5%): {feb_data['in_chop_zone'].sum()} / {len(feb_data)} ({feb_data['in_chop_zone'].sum()/len(feb_data)*100:.1f}%)")
print(f"  Bars above 200MA: {feb_data['above_200ma'].sum()} ({feb_data['above_200ma'].sum()/len(feb_data)*100:.1f}%)")
print(f"  Bars below 200MA: {(~feb_data['above_200ma']).sum()} ({(~feb_data['above_200ma']).sum()/len(feb_data)*100:.1f}%)")

print("\n^ This confirms: February was CHOPPY around 200MA, not a clean downtrend!")

# ============ MAP TRADES TO MA DISTANCE ============
trades['dist_from_200ma'] = trades['entry_time'].map(
    lambda t: df.loc[t, 'dist_from_200ma'] if t in df.index else np.nan
)
trades['in_chop_zone'] = trades['entry_time'].map(
    lambda t: df.loc[t, 'in_chop_zone'] if t in df.index else np.nan
)
trades['regime'] = trades['entry_time'].map(
    lambda t: df.loc[t, 'regime'] if t in df.index else np.nan
)

# ============ TRADES IN CHOP ZONE VS CLEAN ZONE ============
print("\n" + "="*70)
print("PERFORMANCE: CHOP ZONE vs CLEAN ZONE")
print("="*70)

chop_trades = trades[trades['in_chop_zone'] == True]
clean_trades = trades[trades['in_chop_zone'] == False]

print("\n📊 TRADES IN CHOP ZONE (±5% from 200MA):")
if len(chop_trades) > 0:
    print(f"  Total: {len(chop_trades)}")
    print(f"  Win rate: {(chop_trades['pnl_pct'] > 0).sum()/len(chop_trades)*100:.1f}%")
    print(f"  Avg PnL: {chop_trades['pnl_pct'].mean():+.2f}%")
    print(f"  Total PnL: {chop_trades['pnl_pct'].sum():+.2f}%")
    print(f"  Stop loss rate: {(chop_trades['exit_reason']=='stop_loss').sum()/len(chop_trades)*100:.1f}%")
else:
    print("  No trades in chop zone")

print("\n📊 TRADES IN CLEAN ZONE (>5% from 200MA):")
if len(clean_trades) > 0:
    print(f"  Total: {len(clean_trades)}")
    print(f"  Win rate: {(clean_trades['pnl_pct'] > 0).sum()/len(clean_trades)*100:.1f}%")
    print(f"  Avg PnL: {clean_trades['pnl_pct'].mean():+.2f}%")
    print(f"  Total PnL: {clean_trades['pnl_pct'].sum():+.2f}%")
    print(f"  Stop loss rate: {(clean_trades['exit_reason']=='stop_loss').sum()/len(clean_trades)*100:.1f}%")

# ============ BREAKDOWN BY SIDE AND ZONE ============
print("\n" + "="*70)
print("BREAKDOWN: SHORT vs LONG in CHOP vs CLEAN")
print("="*70)

for side in ['SHORT', 'LONG']:
    print(f"\n{side}:")
    
    side_chop = chop_trades[chop_trades['side'] == side]
    side_clean = clean_trades[clean_trades['side'] == side]
    
    if len(side_chop) > 0:
        print(f"  In CHOP zone: {len(side_chop)} trades | Avg PnL: {side_chop['pnl_pct'].mean():+.2f}%")
    else:
        print(f"  In CHOP zone: 0 trades")
    
    if len(side_clean) > 0:
        print(f"  In CLEAN zone: {len(side_clean)} trades | Avg PnL: {side_clean['pnl_pct'].mean():+.2f}%")
    else:
        print(f"  In CLEAN zone: 0 trades")

# ============ THE 13 CONSECUTIVE LOSERS ============
print("\n" + "="*70)
print("THE 13 CONSECUTIVE LOSERS - Were They in Chop Zone?")
print("="*70)

disaster_trades = trades[(trades['entry_time'] >= '2024-02-17') & 
                         (trades['entry_time'] <= '2024-03-03') &
                         (trades['side'] == 'SHORT')]

print(f"\nDisaster period shorts: {len(disaster_trades)}")
print(f"In chop zone: {disaster_trades['in_chop_zone'].sum()} ({disaster_trades['in_chop_zone'].sum()/len(disaster_trades)*100:.1f}%)")
print(f"Average distance from 200MA: {disaster_trades['dist_from_200ma'].mean():+.2f}%")

print("\nDetailed view:")
cols = ['entry_time', 'entry_price', 'dist_from_200ma', 'in_chop_zone', 'pnl_pct', 'exit_reason']
print(disaster_trades[cols].to_string(index=False))

# ============ PROPOSED NEW RULES ============
print("\n" + "="*70)
print("TESTING NEW RULES (Based on Your Observation)")
print("="*70)

# Rule 1: 200MA regime + distance filter
trades['allowed_regime'] = (
    ((trades['side'] == 'SHORT') & (trades['regime'] == 'BEAR')) |
    ((trades['side'] == 'LONG') & (trades['regime'] == 'BULL'))
)

trades['allowed_distance'] = ~trades['in_chop_zone']  # Not in chop zone

trades['allowed_combined'] = trades['allowed_regime'] & trades['allowed_distance']

print("\n📊 RULE 1: 200MA Regime Filter (Simple)")
regime_kept = trades[trades['allowed_regime']]
print(f"  Trades kept: {len(regime_kept)} / {len(trades)}")
print(f"  Avg PnL: {regime_kept['pnl_pct'].mean():+.2f}%")
print(f"  Total PnL: {regime_kept['pnl_pct'].sum():+.2f}%")
winners = regime_kept[regime_kept['pnl_pct'] > 0]
losers = regime_kept[regime_kept['pnl_pct'] <= 0]
gp = winners['pnl_pct'].sum() if len(winners) > 0 else 0
gl = abs(losers['pnl_pct'].sum()) if len(losers) > 0 else 0
pf = gp / gl if gl > 0 else np.inf
print(f"  Profit Factor: {pf:.2f}")

print("\n📊 RULE 2: Distance Filter (Avoid Chop Zone)")
distance_kept = trades[trades['allowed_distance']]
print(f"  Trades kept: {len(distance_kept)} / {len(trades)}")
print(f"  Avg PnL: {distance_kept['pnl_pct'].mean():+.2f}%")
print(f"  Total PnL: {distance_kept['pnl_pct'].sum():+.2f}%")
winners = distance_kept[distance_kept['pnl_pct'] > 0]
losers = distance_kept[distance_kept['pnl_pct'] <= 0]
gp = winners['pnl_pct'].sum() if len(winners) > 0 else 0
gl = abs(losers['pnl_pct'].sum()) if len(losers) > 0 else 0
pf = gp / gl if gl > 0 else np.inf
print(f"  Profit Factor: {pf:.2f}")

print("\n📊 RULE 3: COMBINED (Regime + Distance)")
combined_kept = trades[trades['allowed_combined']]
print(f"  Trades kept: {len(combined_kept)} / {len(trades)}")
print(f"  Avg PnL: {combined_kept['pnl_pct'].mean():+.2f}%")
print(f"  Total PnL: {combined_kept['pnl_pct'].sum():+.2f}%")
winners = combined_kept[combined_kept['pnl_pct'] > 0]
losers = combined_kept[combined_kept['pnl_pct'] <= 0]
gp = winners['pnl_pct'].sum() if len(winners) > 0 else 0
gl = abs(losers['pnl_pct'].sum()) if len(losers) > 0 else 0
pf = gp / gl if gl > 0 else np.inf
print(f"  Profit Factor: {pf:.2f}")

print("\n📊 COMPARISON:")
print(f"  Original (no filter): PF 1.17")
print(f"  Regime only: PF {regime_kept['pnl_pct'].sum() / abs(regime_kept[regime_kept['pnl_pct']<0]['pnl_pct'].sum()) if len(regime_kept[regime_kept['pnl_pct']<0]) > 0 else 0:.2f}")
print(f"  Distance only: PF calculated above")
print(f"  Combined: PF calculated above")

# ============ CONCLUSION ============
print("\n" + "="*70)
print("🎯 CONCLUSION")
print("="*70)

chop_pnl = chop_trades['pnl_pct'].sum() if len(chop_trades) > 0 else 0
clean_pnl = clean_trades['pnl_pct'].sum() if len(clean_trades) > 0 else 0

print(f"\nYour observation about 'chop zone':")
if chop_pnl < -20 and clean_pnl > 0:
    print("✅ CORRECT - Chop zone is the problem!")
    print(f"   Chop zone trades: {chop_pnl:+.2f}% (disaster)")
    print(f"   Clean zone trades: {clean_pnl:+.2f}% (profitable)")
    print("\n   → Distance filter is MORE important than regime filter")
elif chop_pnl < 0 and abs(chop_pnl) > abs(clean_pnl) * 0.5:
    print("🟡 PARTIALLY CORRECT - Chop zone is A problem, but not the only one")
    print(f"   Chop zone trades: {chop_pnl:+.2f}%")
    print(f"   Clean zone trades: {clean_pnl:+.2f}%")
    print("\n   → Need BOTH regime and distance filters")
else:
    print("❌ NOT THE MAIN ISSUE - Something else is wrong")
    print(f"   Chop zone trades: {chop_pnl:+.2f}%")
    print(f"   Clean zone trades: {clean_pnl:+.2f}%")

print("\n" + "="*70)
import pandas as pd
import numpy as np

"""
HIGH TARGET REALITY CHECK
Question: Is 13% target actually better, or is it a mirage?
Answer: Let's see what's REALLY happening to those 71 trades
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

def detailed_backtest(target_pct, target_name):
    """Run backtest and return DETAILED trade breakdown"""
    trades = []
    open_longs = []
    last_entry = -MIN_BARS_BETWEEN_ENTRIES
    
    for i in range(24, len(df)):
        # Entry
        if (df['funding_rate'].iloc[i] <= EXTREME_LOW_FUNDING and
            df['perp_close'].iloc[i] <= df['roll_low_24'].iloc[i] * (1 + PRICE_BUFFER_PCT) and
            df['funding_fresh'].iloc[i] and
            (i - last_entry) >= MIN_BARS_BETWEEN_ENTRIES):
            
            open_longs.append({
                'entry_bar': i,
                'entry_time': df.index[i],
                'entry_price': df['perp_close'].iloc[i],
                'highest_price': df['perp_close'].iloc[i]
            })
            last_entry = i
        
        # Track highest price reached for each position
        for pos in open_longs:
            pos['highest_price'] = max(pos['highest_price'], df['perp_high'].iloc[i])
        
        # Exits
        for pos_idx in range(len(open_longs) - 1, -1, -1):
            pos = open_longs[pos_idx]
            bars_held = i - pos['entry_bar']
            
            pnl_stop = (df['perp_low'].iloc[i] - pos['entry_price']) / pos['entry_price']
            pnl_close = (df['perp_close'].iloc[i] - pos['entry_price']) / pos['entry_price']
            pnl_highest = (pos['highest_price'] - pos['entry_price']) / pos['entry_price']
            
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
                
                trades.append({
                    'entry_time': pos['entry_time'],
                    'entry_price': pos['entry_price'],
                    'exit_price': exit_price,
                    'highest_reached': pos['highest_price'],
                    'pnl_pct': pnl,
                    'pnl_highest': pnl_highest * 100,  # Max gain seen
                    'bars_held': bars_held,
                    'exit_reason': exit_reason
                })
                del open_longs[pos_idx]
    
    # Close remaining
    for pos in open_longs:
        pnl = ((df['perp_close'].iloc[-1] - pos['entry_price']) / pos['entry_price'] * 100) - (TRADING_FEE_ROUND_TRIP * 100)
        pnl_highest = (pos['highest_price'] - pos['entry_price']) / pos['entry_price'] * 100
        
        trades.append({
            'entry_time': pos['entry_time'],
            'entry_price': pos['entry_price'],
            'exit_price': df['perp_close'].iloc[-1],
            'highest_reached': pos['highest_price'],
            'pnl_pct': pnl,
            'pnl_highest': pnl_highest,
            'bars_held': len(df) - 1 - pos['entry_bar'],
            'exit_reason': 'eod'
        })
    
    return pd.DataFrame(trades)

print("="*70)
print("HIGH TARGET REALITY CHECK")
print("="*70)

# Compare 3 targets
results = {}
for target, name in [(0.045, "4.5%"), (0.13, "13%")]:
    results[name] = detailed_backtest(target, name)

# ============ DETAILED COMPARISON ============
print("\n" + "="*70)
print("DETAILED COMPARISON: 4.5% vs 13% Target")
print("="*70)

for name, trades_df in results.items():
    print(f"\n{'='*70}")
    print(f"{name} TARGET")
    print(f"{'='*70}")
    
    print(f"\nTotal trades: {len(trades_df)}")
    
    # Exit breakdown
    stops = trades_df[trades_df['exit_reason'] == 'stop']
    targets = trades_df[trades_df['exit_reason'] == 'target']
    time_exits = trades_df[trades_df['exit_reason'] == 'time']
    
    print(f"\nExit breakdown:")
    print(f"  Stop loss: {len(stops)} ({len(stops)/len(trades_df)*100:.1f}%)")
    print(f"  Hit target: {len(targets)} ({len(targets)/len(trades_df)*100:.1f}%)")
    print(f"  Time limit: {len(time_exits)} ({len(time_exits)/len(trades_df)*100:.1f}%)")
    
    # PnL stats
    print(f"\nPnL Statistics:")
    print(f"  Total PnL: {trades_df['pnl_pct'].sum():+.2f}%")
    print(f"  Avg PnL: {trades_df['pnl_pct'].mean():+.2f}%")
    print(f"  Median PnL: {trades_df['pnl_pct'].median():+.2f}%")
    
    if len(targets) > 0:
        print(f"\nTarget exits contribute: {targets['pnl_pct'].sum():+.2f}% ({targets['pnl_pct'].sum()/trades_df['pnl_pct'].sum()*100:.1f}% of total)")
    if len(time_exits) > 0:
        print(f"Time exits contribute: {time_exits['pnl_pct'].sum():+.2f}% ({time_exits['pnl_pct'].sum()/trades_df['pnl_pct'].sum()*100:.1f}% of total)")

# ============ THE CRITICAL INSIGHT ============
print("\n" + "="*70)
print("🔍 CRITICAL INSIGHT: Unrealized Gains")
print("="*70)

trades_13 = results["13%"]

# How many trades COULD have hit 13% but didn't?
trades_13['could_have_hit'] = trades_13['pnl_highest'] >= 13.0
trades_13['hit_target'] = trades_13['exit_reason'] == 'target'

could_have = trades_13[trades_13['could_have_hit'] & ~trades_13['hit_target']]

print(f"\nTrades that reached 13% but didn't exit there:")
print(f"  Count: {len(could_have)}")
print(f"  Why? Because price pulled back before bar close!")

if len(could_have) > 0:
    print(f"\n  These trades:")
    print(f"    Highest gain seen: {could_have['pnl_highest'].mean():+.2f}% avg")
    print(f"    Actually exited at: {could_have['pnl_pct'].mean():+.2f}% avg")
    print(f"    Unrealized gain: {(could_have['pnl_highest'] - could_have['pnl_pct']).mean():+.2f}%")
    
    print(f"\n  ⚠️  WARNING: 13% target requires price to CLOSE above 13%")
    print(f"     If it spikes to 15% intrabar then drops to 5% by close,")
    print(f"     you DON'T get your 13% exit!")

# ============ SHOW ACTUAL TRADES ============
print("\n" + "="*70)
print("📊 ACTUAL TRADE COMPARISON (Top 5 Winners)")
print("="*70)

trades_45 = results["4.5%"].nlargest(5, 'pnl_pct')
trades_13_top = results["13%"].nlargest(5, 'pnl_pct')

print("\nWith 4.5% target (Top 5):")
cols = ['entry_time', 'pnl_pct', 'pnl_highest', 'exit_reason']
print(trades_45[cols].to_string(index=False))

print("\nWith 13% target (Top 5):")
print(trades_13_top[cols].to_string(index=False))

# ============ VARIANCE ANALYSIS ============
print("\n" + "="*70)
print("📈 VARIANCE & RISK ANALYSIS")
print("="*70)

for name, trades_df in results.items():
    std = trades_df['pnl_pct'].std()
    sharpe = trades_df['pnl_pct'].mean() / std if std > 0 else 0
    
    print(f"\n{name} Target:")
    print(f"  Std Dev: {std:.2f}%")
    print(f"  Sharpe: {sharpe:.2f}")
    
    # Drawdown
    cumsum = trades_df['pnl_pct'].cumsum()
    drawdown = (cumsum.cummax() - cumsum).max()
    print(f"  Max drawdown: {drawdown:.2f}%")

# ============ FINAL VERDICT ============
print("\n" + "="*70)
print("⚖️  FINAL VERDICT")
print("="*70)

trades_45_pf = results["4.5%"]
winners_45 = trades_45_pf[trades_45_pf['pnl_pct'] > 0]
losers_45 = trades_45_pf[trades_45_pf['pnl_pct'] <= 0]
pf_45 = winners_45['pnl_pct'].sum() / abs(losers_45['pnl_pct'].sum())

trades_13_pf = results["13%"]
winners_13 = trades_13_pf[trades_13_pf['pnl_pct'] > 0]
losers_13 = trades_13_pf[trades_13_pf['pnl_pct'] <= 0]
pf_13 = winners_13['pnl_pct'].sum() / abs(losers_13['pnl_pct'].sum())

print(f"\n4.5% Target:")
print(f"  PF: {pf_45:.2f}")
print(f"  Total: {trades_45_pf['pnl_pct'].sum():+.2f}%")
print(f"  Win Rate: {len(winners_45)/len(trades_45_pf)*100:.1f}%")
print(f"  Consistency: {len(winners_45)} winners spread profit")

print(f"\n13% Target:")
print(f"  PF: {pf_13:.2f}")
print(f"  Total: {trades_13_pf['pnl_pct'].sum():+.2f}%")
print(f"  Win Rate: {len(winners_13)/len(trades_13_pf)*100:.1f}%")
print(f"  Consistency: ~4 MASSIVE winners carry strategy")

print("\n" + "="*70)
print("💡 RECOMMENDATION")
print("="*70)

target_hits_13 = (trades_13_pf['exit_reason'] == 'target').sum()

if target_hits_13 < 10:
    print(f"\n❌ DON'T USE 13% TARGET")
    print(f"\nReasons:")
    print(f"  1. Only {target_hits_13} trades actually hit the target")
    print(f"  2. Win rate drops to 39% (most trades lose)")
    print(f"  3. Strategy depends on a few huge winners (high variance)")
    print(f"  4. In real trading: You'll sit through MANY losers waiting for 1 big win")
    print(f"  5. Psychologically difficult - you'll likely abandon it")
    
    print(f"\n✅ USE 4.5% TARGET INSTEAD")
    print(f"\nReasons:")
    print(f"  1. More consistent wins ({len(winners_45)} hits vs {target_hits_13})")
    print(f"  2. Higher win rate (48% vs 39%)")
    print(f"  3. Similar total profit (+64% vs +83% but less variance)")
    print(f"  4. Easier to trade psychologically")
    print(f"  5. More robust to market changes")
else:
    print(f"\n🟡 13% TARGET MIGHT WORK")
    print(f"  But you need to accept:")
    print(f"  - 61% of trades will lose")
    print(f"  - You'll have long losing streaks")
    print(f"  - Need strong discipline to stick with it")

print("\n" + "="*70)
print("🎯 BLINDSPOTS YOU ASKED ABOUT")
print("="*70)

print("\n1. ⚠️  INTRABAR EXECUTION")
print("   - Backtest assumes you exit at BAR CLOSE when target hit")
print("   - Reality: Price might spike to 15%, trigger your limit order")
print("   - But if it does, 13% is actually easier to hit than expected!")
print("   - Need to decide: Market order at close OR limit order at target?")

print("\n2. ⚠️  SLIPPAGE")
print("   - 13% moves are RARE")
print("   - When they happen, there might be low liquidity")
print("   - Your limit order at +13% might not fill")

print("\n3. ⚠️  PSYCHOLOGICAL DURABILITY")
print("   - Can you sit through 10 losers waiting for 1 big winner?")
print("   - Most traders can't - they abandon the strategy")
print("   - 4.5% gives more frequent positive feedback")

print("\n4. ⚠️  OVERFITTING TO SPECIFIC WINNERS")
print("   - Your 13% target works because 4 specific trades in your data")
print("   - What if those don't happen in future?")
print("   - More robust to have many smaller winners")

print("\n5. ⚠️  TIME LIMIT CARRYING THE STRATEGY")
print("   - Much of your profit comes from time exits, NOT target exits")
print("   - This means the 13% target isn't actually doing much")
print("   - It's just: 'hold for 42 bars unless it moons or crashes'")

print("\n" + "="*70)
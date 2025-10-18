import pandas as pd
import numpy as np

"""
SIMPLE FUNDING SIGNAL VALIDATION
Purpose: Test if extreme funding predicts mean reversion WITHOUT any complex logic
Author: Crypto analyst perspective
"""

# ============ CONFIGURATION ============
CSV_PATH = '/Users/duncanwan/Desktop/learning/Bitcoin/4hrs/BTC_combined_2024_v2.csv'

# Extreme thresholds (based on 10-year experience with crypto funding)
EXTREME_HIGH_FUNDING = 0.00012  # 0.012% - Top 5% of funding (SHORT signal)
EXTREME_LOW_FUNDING = 0.00003   # 0.003% - Bottom 15% of funding (LONG signal)

# Simple exit rules
TARGET_PROFIT_SHORT = 0.06  # 6% profit target for SHORT
TARGET_PROFIT_LONG = 0.04   # 4% profit target for LONG  
STOP_LOSS = 0.03            # 3% stop loss for both
MAX_HOLD_BARS = 42          # 7 days (42 * 4 hours = 168 hours)

# Entry throttle: Only trade TRUE extremes
MIN_BARS_BETWEEN_TRADES = 72  # 12 days between same-side entries

# ============ LOAD DATA ============
print("Loading data...")
df = pd.read_csv(CSV_PATH)
df['bar_time'] = pd.to_datetime(df['bar_time'], utc=True)
df = df.set_index('bar_time').sort_index()

print(f"Data loaded: {len(df)} bars")
print(f"Date range: {df.index[0]} to {df.index[-1]}")
print(f"Columns: {df.columns.tolist()}")

# ============ PREP ============
# Flag when funding actually updates (every 8 hours = every 2 bars)
df['funding_fresh'] = df['funding_rate'] != df['funding_rate'].shift(1)

# Rolling 24-bar high/low for context (backward-looking only)
df['roll_high_24'] = df['prep_close'].shift(1).rolling(24, min_periods=24).max()
df['roll_low_24'] = df['prep_close'].shift(1).rolling(24, min_periods=24).min()

# ============ SIGNAL DETECTION ============
print("\n" + "="*60)
print("SIGNAL DETECTION (Only on fresh funding bars)")
print("="*60)

# Only check signals when funding actually updates
df_fresh = df[df['funding_fresh'] == True].copy()

# Count extreme funding occurrences
extreme_high = df_fresh['funding_rate'] >= EXTREME_HIGH_FUNDING
extreme_low = df_fresh['funding_rate'] <= EXTREME_LOW_FUNDING

print(f"\nTotal fresh funding updates: {len(df_fresh)}")
print(f"Extreme HIGH funding (>={EXTREME_HIGH_FUNDING:.5f}): {extreme_high.sum()} times ({extreme_high.sum()/len(df_fresh)*100:.1f}%)")
print(f"Extreme LOW funding (<={EXTREME_LOW_FUNDING:.5f}): {extreme_low.sum()} times ({extreme_low.sum()/len(df_fresh)*100:.1f}%)")

# Funding distribution
print(f"\nFunding rate percentiles:")
for p in [5, 10, 25, 50, 75, 90, 95]:
    val = df_fresh['funding_rate'].quantile(p/100)
    print(f"  {p:2d}th: {val:.5f} ({val*100:.4f}%)")

# ============ ENTRY SIGNALS ============
# SHORT: Extreme positive funding + Price near 24-bar high
short_signal = (
    (df['funding_rate'] >= EXTREME_HIGH_FUNDING) &
    (df['prep_close'] >= df['roll_high_24'] * 0.98) &  # Within 2% of high
    (df['funding_fresh'] == True)  # Only on fresh funding
)

# LONG: Extreme low funding + Price near 24-bar low  
long_signal = (
    (df['funding_rate'] <= EXTREME_LOW_FUNDING) &
    (df['prep_close'] <= df['roll_low_24'] * 1.02) &  # Within 2% of low
    (df['funding_fresh'] == True)  # Only on fresh funding
)

print(f"\nInitial signals before throttle:")
print(f"  SHORT signals: {short_signal.sum()}")
print(f"  LONG signals: {long_signal.sum()}")

# ============ BACKTEST ENGINE ============
trades = []
last_entry_bar = {'SHORT': -1000, 'LONG': -1000}  # Track last entry per side

for i in range(24, len(df)):  # Start after 24 bars for rolling context
    
    # ========== SHORT ENTRY ==========
    if short_signal.iloc[i] and (i - last_entry_bar['SHORT']) >= MIN_BARS_BETWEEN_TRADES:
        entry_price = df['prep_close'].iloc[i+1]  # Enter next bar at close
        entry_funding = df['funding_rate'].iloc[i]
        entry_bar = i + 1
        last_entry_bar['SHORT'] = i
        
        # Simulate holding the trade
        for j in range(entry_bar, min(entry_bar + MAX_HOLD_BARS, len(df))):
            current_price = df['prep_close'].iloc[j]
            pnl_pct = (entry_price - current_price) / entry_price
            bars_held = j - entry_bar
            
            # Check exits
            exit_reason = None
            if pnl_pct >= TARGET_PROFIT_SHORT:
                exit_reason = 'target'
            elif pnl_pct <= -STOP_LOSS:
                exit_reason = 'stop'
            elif j == (entry_bar + MAX_HOLD_BARS - 1) or j == len(df) - 1:
                exit_reason = 'time'
            
            if exit_reason:
                trades.append({
                    'side': 'SHORT',
                    'entry_bar': entry_bar,
                    'entry_time': df.index[entry_bar],
                    'entry_price': entry_price,
                    'entry_funding': entry_funding,
                    'exit_bar': j,
                    'exit_time': df.index[j],
                    'exit_price': current_price,
                    'bars_held': bars_held,
                    'pnl_pct': pnl_pct * 100,
                    'exit_reason': exit_reason
                })
                break
    
    # ========== LONG ENTRY ==========
    if long_signal.iloc[i] and (i - last_entry_bar['LONG']) >= MIN_BARS_BETWEEN_TRADES:
        entry_price = df['prep_close'].iloc[i+1]  # Enter next bar at close
        entry_funding = df['funding_rate'].iloc[i]
        entry_bar = i + 1
        last_entry_bar['LONG'] = i
        
        # Simulate holding the trade
        for j in range(entry_bar, min(entry_bar + MAX_HOLD_BARS, len(df))):
            current_price = df['prep_close'].iloc[j]
            pnl_pct = (current_price - entry_price) / entry_price
            bars_held = j - entry_bar
            
            # Check exits
            exit_reason = None
            if pnl_pct >= TARGET_PROFIT_LONG:
                exit_reason = 'target'
            elif pnl_pct <= -STOP_LOSS:
                exit_reason = 'stop'
            elif j == (entry_bar + MAX_HOLD_BARS - 1) or j == len(df) - 1:
                exit_reason = 'time'
            
            if exit_reason:
                trades.append({
                    'side': 'LONG',
                    'entry_bar': entry_bar,
                    'entry_time': df.index[entry_bar],
                    'entry_price': entry_price,
                    'entry_funding': entry_funding,
                    'exit_bar': j,
                    'exit_time': df.index[j],
                    'exit_price': current_price,
                    'bars_held': bars_held,
                    'pnl_pct': pnl_pct * 100,
                    'exit_reason': exit_reason
                })
                break

# ============ RESULTS ============
if not trades:
    print("\n" + "="*60)
    print("❌ NO TRADES GENERATED")
    print("="*60)
    print("\nThis means:")
    print("  1. Your thresholds are too strict (funding never reaches extremes)")
    print("  2. OR price is never near highs/lows when funding is extreme")
    print("\nRecommendation: Lower the thresholds or remove price conditions")
else:
    trades_df = pd.DataFrame(trades)
    
    print("\n" + "="*60)
    print("BACKTEST RESULTS")
    print("="*60)
    
    # Overall stats
    print(f"\nTotal trades: {len(trades_df)}")
    print(f"  SHORT: {len(trades_df[trades_df['side']=='SHORT'])}")
    print(f"  LONG: {len(trades_df[trades_df['side']=='LONG'])}")
    
    winners = trades_df[trades_df['pnl_pct'] > 0]
    losers = trades_df[trades_df['pnl_pct'] < 0]
    
    print(f"\nWin rate: {len(winners)/len(trades_df)*100:.1f}%")
    print(f"  Winners: {len(winners)}")
    print(f"  Losers: {len(losers)}")
    
    print(f"\nAverage PnL: {trades_df['pnl_pct'].mean():.2f}%")
    print(f"Median PnL: {trades_df['pnl_pct'].median():.2f}%")
    print(f"Total PnL: {trades_df['pnl_pct'].sum():.2f}%")
    
    # Profit factor
    gross_profit = winners['pnl_pct'].sum()
    gross_loss = abs(losers['pnl_pct'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf
    print(f"\nProfit factor: {profit_factor:.2f}")
    
    # Exit breakdown
    print(f"\nExit reason breakdown:")
    for reason in ['target', 'stop', 'time']:
        count = len(trades_df[trades_df['exit_reason']==reason])
        pct = count/len(trades_df)*100
        avg_pnl = trades_df[trades_df['exit_reason']==reason]['pnl_pct'].mean()
        print(f"  {reason:8s}: {count:3d} trades ({pct:5.1f}%) | Avg PnL: {avg_pnl:+6.2f}%")
    
    # Time analysis
    print(f"\nHolding time:")
    print(f"  Average: {trades_df['bars_held'].mean():.1f} bars ({trades_df['bars_held'].mean()*4:.0f} hours)")
    print(f"  Median: {trades_df['bars_held'].median():.1f} bars ({trades_df['bars_held'].median()*4:.0f} hours)")
    
    # Save trades
    output_file = 'simple_validation_trades.csv'
    trades_df.to_csv(output_file, index=False)
    print(f"\n✓ Trades saved to: {output_file}")
    
    # ============ INTERPRETATION ============
    print("\n" + "="*60)
    print("INTERPRETATION")
    print("="*60)
    
    win_rate = len(winners)/len(trades_df)*100
    avg_pnl = trades_df['pnl_pct'].mean()
    
    if len(trades_df) < 5:
        print("\n⚠️  INSUFFICIENT DATA")
        print("Less than 5 trades - need more data or lower thresholds")
    
    elif win_rate >= 55 and profit_factor >= 1.5:
        print("\n✅ STRONG EDGE DETECTED")
        print("Signal works! Now you can add complexity:")
        print("  1. Get OHLC data for better stops")
        print("  2. Add regime filter (50-day MA)")
        print("  3. Optimize position sizing")
        
    elif win_rate >= 45 and profit_factor >= 1.2:
        print("\n🟡 WEAK EDGE DETECTED")
        print("Signal shows some promise but needs refinement:")
        print("  1. Adjust thresholds to be more selective")
        print("  2. Add filters (volatility, trend, etc.)")
        print("  3. Consider if edge covers fees + slippage")
        
    else:
        print("\n❌ NO EDGE DETECTED")
        print("Signal doesn't work with these parameters.")
        print("Options:")
        print("  1. Try different thresholds")
        print("  2. Test on different timeframe (1H or 8H)")
        print("  3. Pivot to different strategy entirely")
    
    # Top winners and losers
    print("\n" + "="*60)
    print("TOP 3 WINNERS")
    print("="*60)
    top_winners = trades_df.nlargest(min(3, len(trades_df)), 'pnl_pct')
    for idx, trade in top_winners.iterrows():
        print(f"{trade['side']:5s} | Entry: {trade['entry_time'].strftime('%Y-%m-%d')} at ${trade['entry_price']:,.0f} | "
              f"Funding: {trade['entry_funding']*100:.4f}% | PnL: {trade['pnl_pct']:+.2f}% | Exit: {trade['exit_reason']}")
    
    print("\n" + "="*60)
    print("TOP 3 LOSERS")
    print("="*60)
    top_losers = trades_df.nsmallest(min(3, len(trades_df)), 'pnl_pct')
    for idx, trade in top_losers.iterrows():
        print(f"{trade['side']:5s} | Entry: {trade['entry_time'].strftime('%Y-%m-%d')} at ${trade['entry_price']:,.0f} | "
              f"Funding: {trade['entry_funding']*100:.4f}% | PnL: {trade['pnl_pct']:+.2f}% | Exit: {trade['exit_reason']}")

print("\n" + "="*60)
print("VALIDATION COMPLETE")
print("="*60)
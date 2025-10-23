import pandas as pd
import numpy as np

"""
SIMPLE FUNDING STRATEGY BACKTEST - UPDATED
- Multiple same-side positions allowed
- No opposing positions (SHORT blocks LONG, vice versa)
- 6-bar minimum between same-side entries
- Trading fees included (0.08% round trip)
"""

# ============ CONFIGURATION ============
#CSV_PATH = '/Users/duncanwan/Desktop/learning/Bitcoin/BTC_perp_funding_combined_OHLC.csv'
CSV_PATH = '/Users/duncanwan/Desktop/learning/Bitcoin/BTC_perp_funding_combined_OHLC.csv'
CSV_PATH = r'C:\Users\Duncan Wan\Desktop\VSCODE\BTC_perp_funding_combined_OHLC.csv'

# Entry thresholds
EXTREME_HIGH_FUNDING = 0.00012  # 0.012% for SHORT
EXTREME_LOW_FUNDING = 0.00003   # 0.003% for LONG

# Price buffer (how close to high/low for entry)
PRICE_BUFFER_PCT = 0.03  # 3% buffer (try 0.03, 0.04, or 0.05)

# Exit parameters
STOP_LOSS_SHORT = 0.03      # 3% stop loss for SHORT
PROFIT_TARGET_SHORT = 0.06  # 6% profit target for SHORT
STOP_LOSS_LONG = 0.03       # 3% stop loss for LONG
PROFIT_TARGET_LONG = 0.04   # 4% profit target for LONG
TIME_LIMIT_BARS = 42        # 7 days = 42 bars (4H data)

# Entry throttling
MIN_BARS_BETWEEN_ENTRIES = 6  # 1 day minimum between same-side entries

# Trading fees
TAKER_FEE = 0.0004  # 0.04% per side
TRADING_FEE_ROUND_TRIP = TAKER_FEE * 2  # 0.08% total

# ============ LOAD DATA ============
print("Loading data...")
df = pd.read_csv(CSV_PATH)
df['bar_time'] = pd.to_datetime(df['bar_time'], utc=True)
df = df.set_index('bar_time').sort_index()

print(f"✓ Loaded {len(df)} bars")
print(f"✓ Date range: {df.index[0]} to {df.index[-1]}")
print(f"✓ Duration: {(df.index[-1] - df.index[0]).days} days\n")

# ============ PREP INDICATORS ============
# Detect when funding actually updates
df['funding_fresh'] = df['funding_rate'] != df['funding_rate'].shift(1)

# Rolling 24-bar high/low (backward-looking only)
df['roll_high_24'] = df['perp_close'].shift(1).rolling(24, min_periods=24).max()
df['roll_low_24'] = df['perp_close'].shift(1).rolling(24, min_periods=24).min()

# ============ ENTRY SIGNALS ============
# SHORT: Extreme positive funding + Price near 24-bar high + Funding just updated
short_signal = (
    (df['funding_rate'] >= EXTREME_HIGH_FUNDING) &
    (df['perp_close'] >= df['roll_high_24'] * (1 - PRICE_BUFFER_PCT)) &
    (df['funding_fresh'] == True)
)

# LONG: Extreme low funding + Price near 24-bar low + Funding just updated
long_signal = (
    (df['funding_rate'] <= EXTREME_LOW_FUNDING) &
    (df['perp_close'] <= df['roll_low_24'] * (1 + PRICE_BUFFER_PCT)) &
    (df['funding_fresh'] == True)
)

print("="*70)
print("CONFIGURATION")
print("="*70)
print(f"Price buffer: {PRICE_BUFFER_PCT*100:.0f}%")
print(f"  SHORT enters if price >= {(1-PRICE_BUFFER_PCT)*100:.0f}% of 24-bar high")
print(f"  LONG enters if price <= {(1+PRICE_BUFFER_PCT)*100:.0f}% of 24-bar low")
print(f"Trading fees: {TRADING_FEE_ROUND_TRIP*100:.2f}% per trade")
print(f"Min bars between entries: {MIN_BARS_BETWEEN_ENTRIES} bars ({MIN_BARS_BETWEEN_ENTRIES*4}h)")

print("\n" + "="*70)
print("SIGNAL DETECTION")
print("="*70)
print(f"Total bars: {len(df)}")
print(f"Fresh funding updates: {df['funding_fresh'].sum()}")
print(f"Potential SHORT signals: {short_signal.sum()}")
print(f"Potential LONG signals: {long_signal.sum()}")

# ============ BACKTEST ENGINE ============
trades = []
open_shorts = []  # List of open SHORT positions
open_longs = []   # List of open LONG positions
last_short_entry_bar = -MIN_BARS_BETWEEN_ENTRIES  # Track last entry for throttling
last_long_entry_bar = -MIN_BARS_BETWEEN_ENTRIES

for i in range(24, len(df)):  # Start after 24 bars for rolling context
    
    # ========== SHORT ENTRY ==========
    # Only enter SHORT if: signal triggers, throttle period passed, and NO LONG positions
    if (short_signal.iloc[i] and 
        (i - last_short_entry_bar) >= MIN_BARS_BETWEEN_ENTRIES and
        len(open_longs) == 0):
        
        open_shorts.append({
            'entry_bar': i,
            'entry_time': df.index[i],
            'entry_price': df['perp_close'].iloc[i],
            'entry_funding': df['funding_rate'].iloc[i]
        })
        last_short_entry_bar = i
    
    # ========== SHORT EXITS ==========
    for pos_idx in range(len(open_shorts) - 1, -1, -1):  # Iterate backwards for safe removal
        pos = open_shorts[pos_idx]
        bars_held = i - pos['entry_bar']
        current_high = df['perp_high'].iloc[i]
        current_close = df['perp_close'].iloc[i]
        
        # Calculate PnL (price movement only, fees added later)
        pnl_pct_stop = (pos['entry_price'] - current_high) / pos['entry_price']
        pnl_pct_close = (pos['entry_price'] - current_close) / pos['entry_price']
        
        exit_reason = None
        exit_price = None
        
        # Check exits (priority order)
        if pnl_pct_stop <= -STOP_LOSS_SHORT:
            exit_reason = 'stop_loss'
            exit_price = pos['entry_price'] * (1 + STOP_LOSS_SHORT)
        elif pnl_pct_close >= PROFIT_TARGET_SHORT:
            exit_reason = 'profit_target'
            exit_price = current_close
        elif bars_held >= TIME_LIMIT_BARS:
            exit_reason = 'time_limit'
            exit_price = current_close
        
        if exit_reason:
            pnl_before_fees = (pos['entry_price'] - exit_price) / pos['entry_price'] * 100
            pnl_after_fees = pnl_before_fees - (TRADING_FEE_ROUND_TRIP * 100)
            
            trades.append({
                'entry_time': pos['entry_time'],
                'exit_time': df.index[i],
                'side': 'SHORT',
                'entry_price': pos['entry_price'],
                'exit_price': exit_price,
                'entry_funding': pos['entry_funding'],
                'bars_held': bars_held,
                'pnl_pct': pnl_after_fees,
                'exit_reason': exit_reason
            })
            del open_shorts[pos_idx]
    
    # ========== LONG ENTRY ==========
    # Only enter LONG if: signal triggers, throttle period passed, and NO SHORT positions
    if (long_signal.iloc[i] and 
        (i - last_long_entry_bar) >= MIN_BARS_BETWEEN_ENTRIES and
        len(open_shorts) == 0):
        
        open_longs.append({
            'entry_bar': i,
            'entry_time': df.index[i],
            'entry_price': df['perp_close'].iloc[i],
            'entry_funding': df['funding_rate'].iloc[i]
        })
        last_long_entry_bar = i
    
    # ========== LONG EXITS ==========
    for pos_idx in range(len(open_longs) - 1, -1, -1):
        pos = open_longs[pos_idx]
        bars_held = i - pos['entry_bar']
        current_low = df['perp_low'].iloc[i]
        current_close = df['perp_close'].iloc[i]
        
        # Calculate PnL
        pnl_pct_stop = (current_low - pos['entry_price']) / pos['entry_price']
        pnl_pct_close = (current_close - pos['entry_price']) / pos['entry_price']
        
        exit_reason = None
        exit_price = None
        
        # Check exits (priority order)
        if pnl_pct_stop <= -STOP_LOSS_LONG:
            exit_reason = 'stop_loss'
            exit_price = pos['entry_price'] * (1 - STOP_LOSS_LONG)
        elif pnl_pct_close >= PROFIT_TARGET_LONG:
            exit_reason = 'profit_target'
            exit_price = current_close
        elif bars_held >= TIME_LIMIT_BARS:
            exit_reason = 'time_limit'
            exit_price = current_close
        
        if exit_reason:
            pnl_before_fees = (exit_price - pos['entry_price']) / pos['entry_price'] * 100
            pnl_after_fees = pnl_before_fees - (TRADING_FEE_ROUND_TRIP * 100)
            
            trades.append({
                'entry_time': pos['entry_time'],
                'exit_time': df.index[i],
                'side': 'LONG',
                'entry_price': pos['entry_price'],
                'exit_price': exit_price,
                'entry_funding': pos['entry_funding'],
                'bars_held': bars_held,
                'pnl_pct': pnl_after_fees,
                'exit_reason': exit_reason
            })
            del open_longs[pos_idx]

# Close remaining positions at end
for pos in open_shorts:
    pnl_before_fees = (pos['entry_price'] - df['perp_close'].iloc[-1]) / pos['entry_price'] * 100
    pnl_after_fees = pnl_before_fees - (TRADING_FEE_ROUND_TRIP * 100)
    trades.append({
        'entry_time': pos['entry_time'],
        'exit_time': df.index[-1],
        'side': 'SHORT',
        'entry_price': pos['entry_price'],
        'exit_price': df['perp_close'].iloc[-1],
        'entry_funding': pos['entry_funding'],
        'bars_held': len(df) - 1 - pos['entry_bar'],
        'pnl_pct': pnl_after_fees,
        'exit_reason': 'end_of_data'
    })

for pos in open_longs:
    pnl_before_fees = (df['perp_close'].iloc[-1] - pos['entry_price']) / pos['entry_price'] * 100
    pnl_after_fees = pnl_before_fees - (TRADING_FEE_ROUND_TRIP * 100)
    trades.append({
        'entry_time': pos['entry_time'],
        'exit_time': df.index[-1],
        'side': 'LONG',
        'entry_price': pos['entry_price'],
        'exit_price': df['perp_close'].iloc[-1],
        'entry_funding': pos['entry_funding'],
        'bars_held': len(df) - 1 - pos['entry_bar'],
        'pnl_pct': pnl_after_fees,
        'exit_reason': 'end_of_data'
    })

# ============ RESULTS ============
if not trades:
    print("\n" + "="*70)
    print("❌ NO TRADES GENERATED")
    print("="*70)
    print("\nPossible reasons:")
    print("  1. Funding never reached extreme levels")
    print("  2. Price was never close enough to highs/lows")
    print(f"  3. Price buffer ({PRICE_BUFFER_PCT*100:.0f}%) is too tight")
    print("\nSuggestions:")
    print("  - Lower funding thresholds")
    print("  - Increase PRICE_BUFFER_PCT to 0.05 (5%)")
    
else:
    trades_df = pd.DataFrame(trades)
    
    print("\n" + "="*70)
    print("BACKTEST RESULTS")
    print("="*70)
    
    # Overall stats
    print(f"\n📊 TRADE SUMMARY:")
    print(f"Total trades: {len(trades_df)}")
    print(f"  SHORT trades: {len(trades_df[trades_df['side']=='SHORT'])}")
    print(f"  LONG trades: {len(trades_df[trades_df['side']=='LONG'])}")
    
    # Win/Loss
    winners = trades_df[trades_df['pnl_pct'] > 0]
    losers = trades_df[trades_df['pnl_pct'] <= 0]
    
    print(f"\n📈 WIN/LOSS:")
    print(f"Win rate: {len(winners)/len(trades_df)*100:.1f}%")
    print(f"  Winners: {len(winners)}")
    print(f"  Losers: {len(losers)}")
    
    # PnL stats
    print(f"\n💰 PnL STATISTICS (After Fees):")
    print(f"Average PnL: {trades_df['pnl_pct'].mean():+.2f}%")
    print(f"Median PnL: {trades_df['pnl_pct'].median():+.2f}%")
    print(f"Total PnL: {trades_df['pnl_pct'].sum():+.2f}%")
    print(f"Best trade: {trades_df['pnl_pct'].max():+.2f}%")
    print(f"Worst trade: {trades_df['pnl_pct'].min():+.2f}%")
    
    # Profit factor
    gross_profit = winners['pnl_pct'].sum() if len(winners) > 0 else 0
    gross_loss = abs(losers['pnl_pct'].sum()) if len(losers) > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf
    
    print(f"\n🎯 KEY METRIC:")
    print(f"Profit Factor: {profit_factor:.2f}")
    if profit_factor >= 1.5:
        print("  ✅ STRONG - Strategy has edge!")
    elif profit_factor >= 1.2:
        print("  🟡 WEAK - Marginal edge, needs optimization")
    elif profit_factor >= 1.0:
        print("  ⚠️  BREAKEVEN - No clear edge")
    else:
        print("  ❌ LOSING - Strategy doesn't work")
    
    # Exit breakdown
    print(f"\n🚪 EXIT BREAKDOWN:")
    for reason in ['stop_loss', 'profit_target', 'time_limit', 'end_of_data']:
        subset = trades_df[trades_df['exit_reason']==reason]
        if len(subset) > 0:
            count = len(subset)
            pct = count/len(trades_df)*100
            avg_pnl = subset['pnl_pct'].mean()
            print(f"  {reason:15s}: {count:3d} trades ({pct:5.1f}%) | Avg PnL: {avg_pnl:+6.2f}%")
    
    # Holding time
    print(f"\n⏱️  HOLDING TIME:")
    print(f"Average: {trades_df['bars_held'].mean():.1f} bars ({trades_df['bars_held'].mean()*4:.0f} hours)")
    print(f"Median: {trades_df['bars_held'].median():.0f} bars ({trades_df['bars_held'].median()*4:.0f} hours)")
    
    # Save results
    output_file = 'simple_strategy_trades.csv'
    trades_df.to_csv(output_file, index=False)
    print(f"\n✅ Trades saved to: {output_file}")
    
    # Show sample trades
    print("\n" + "="*70)
    print("SAMPLE TRADES (First 10)")
    print("="*70)
    cols = ['entry_time', 'side', 'entry_price', 'exit_price', 'bars_held', 'pnl_pct', 'exit_reason']
    print(trades_df[cols].head(10).to_string(index=False))

print("\n" + "="*70)
print("BACKTEST COMPLETE")
print("="*70)
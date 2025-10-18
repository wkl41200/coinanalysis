import pandas as pd
import numpy as np

"""
COMBINE PERP OHLC + FUNDING RATE
Simplified script - perp only, no spot needed
"""

# ============ FILE PATHS ============
PERP_FILE = '/Users/duncanwan/Desktop/learning/Bitcoin/4hrs/future/cleaned/BTCUSDT_4h_2024_all.csv'
FUNDING_FILE = '/Users/duncanwan/Desktop/learning/Bitcoin/4hrs/funding/cleaned/BTCUSDT_funding_combined.csv'
OUTPUT_FILE = 'BTC_perp_funding_combined_OHLC.csv'

print("="*80)
print("COMBINING PERP OHLC + FUNDING RATE")
print("="*80)

# ============ LOAD PERP DATA ============
print("\nStep 1: Loading perp OHLC data...")
perp = pd.read_csv(PERP_FILE)

print(f"  Columns: {perp.columns.tolist()}")
print(f"  Rows: {len(perp)}")

# Rename columns to standard format
perp = perp.rename(columns={
    'close_time': 'bar_time',  # Use close_time as the bar timestamp
    'open': 'perp_open',
    'high': 'perp_high',
    'low': 'perp_low',
    'close': 'perp_close',
    'volume': 'perp_volume'
})

# Convert bar_time to datetime (remove milliseconds)
perp['bar_time'] = pd.to_datetime(perp['bar_time'], utc=True, errors='coerce')



# Round to nearest hour (removes :59:59.999)
perp['bar_time'] = perp['bar_time'].dt.floor('H')

# Sort and deduplicate
perp = perp.sort_values('bar_time').drop_duplicates('bar_time')

print(f"  Date range: {perp['bar_time'].min()} to {perp['bar_time'].max()}")
print(f"  Price range: ${perp['perp_close'].min():,.0f} to ${perp['perp_close'].max():,.0f}")

# ============ LOAD FUNDING ============
print("\nStep 2: Loading funding rate data...")
funding = pd.read_csv(FUNDING_FILE)

print(f"  Columns: {funding.columns.tolist()}")
print(f"  Rows: {len(funding)}")

# Rename funding columns
funding = funding.rename(columns={
    'calc_time': 'bar_time',
    'last_funding_rate': 'funding_rate'
})

# Convert to datetime
funding['bar_time'] = pd.to_datetime(funding['bar_time'], utc=True,errors='coerce')

funding = funding.dropna(subset=['bar_time'])
funding = funding.sort_values('bar_time').drop_duplicates('bar_time')


# Sort and deduplicate
funding = funding.sort_values('bar_time').drop_duplicates('bar_time')

print(f"  Date range: {funding['bar_time'].min()} to {funding['bar_time'].max()}")
print(f"  Funding rate range: {funding['funding_rate'].min():.6f} to {funding['funding_rate'].max():.6f}")

# Check funding update frequency
funding['hour'] = funding['bar_time'].dt.hour
print(f"  Funding update hours: {sorted(funding['hour'].unique())}")
print(f"  Expected: [0, 8, 16] for 8-hour funding cycle")

# ============ MERGE USING BACKWARD FILL ============
print("\nStep 3: Merging with backward fill...")
print("  Logic: Each 4H bar gets the most recent funding rate")
print("  Example: 04:00 bar uses 00:00 funding (no update yet)")
print("           08:00 bar uses 08:00 funding (just updated)")
print("           12:00 bar uses 08:00 funding (no update yet)")

# Select only the columns we need from perp
perp_final = perp[['bar_time', 'perp_open', 'perp_high', 'perp_low', 
                   'perp_close', 'perp_volume']].copy()

# Merge using backward fill (funding fills forward until next update)
combined = pd.merge_asof(
    perp_final.sort_values('bar_time'),
    funding[['bar_time', 'funding_rate']].sort_values('bar_time'),
    on='bar_time',
    direction='backward',
    tolerance=pd.Timedelta('12 hours')  # Max gap allowed
)

# ============ VALIDATION ============
print("\nStep 4: Validating merged data...")

# Check for missing values
print(f"  Total rows: {len(combined)}")
print(f"  Missing funding rate: {combined['funding_rate'].isna().sum()}")
print(f"  Missing OHLC: {combined[['perp_open','perp_high','perp_low','perp_close']].isna().sum().sum()}")

# Remove rows with missing funding (if any at the start)
before_drop = len(combined)
combined = combined.dropna(subset=['funding_rate'])
after_drop = len(combined)

if before_drop > after_drop:
    print(f"  Dropped {before_drop - after_drop} rows with missing funding (likely at start of dataset)")

# Check OHLC logic
ohlc_valid = (
    (combined['perp_high'] >= combined['perp_close']) &
    (combined['perp_high'] >= combined['perp_open']) &
    (combined['perp_low'] <= combined['perp_close']) &
    (combined['perp_low'] <= combined['perp_open']) &
    (combined['perp_high'] >= combined['perp_low'])
)

print(f"  OHLC logic valid: {ohlc_valid.sum()} / {len(combined)} bars ({ohlc_valid.sum()/len(combined)*100:.1f}%)")

if not ohlc_valid.all():
    invalid_count = (~ohlc_valid).sum()
    print(f"  ⚠️  WARNING: {invalid_count} bars have invalid OHLC")
    invalid_bars = combined[~ohlc_valid].head(3)
    print("  First few invalid bars:")
    print(invalid_bars[['bar_time', 'perp_open', 'perp_high', 'perp_low', 'perp_close']])

# Check funding update frequency
combined['funding_changed'] = combined['funding_rate'] != combined['funding_rate'].shift(1)
funding_changes_per_day = combined.groupby(combined['bar_time'].dt.date)['funding_changed'].sum()
avg_updates = funding_changes_per_day.mean()

print(f"  Avg funding updates per day: {avg_updates:.1f} (should be ~3 for 8-hour cycle)")

if avg_updates < 2.5 or avg_updates > 3.5:
    print(f"  ⚠️  WARNING: Expected 3 updates/day, got {avg_updates:.1f}")

# Verify forward-fill is working
print("\n  Checking forward-fill logic (sample 10 bars):")
sample = combined.iloc[0:10][['bar_time', 'funding_rate', 'funding_changed']]
print(sample.to_string(index=False))

# ============ SAVE ============
print("\nStep 5: Saving combined data...")

combined_final = combined[['bar_time', 'perp_open', 'perp_high', 'perp_low', 
                           'perp_close', 'perp_volume', 'funding_rate']].copy()

combined_final.to_csv(OUTPUT_FILE, index=False)

print(f"\n✅ SUCCESS!")
print(f"  Saved to: {OUTPUT_FILE}")
print(f"  Total bars: {len(combined_final)}")
print(f"  Date range: {combined_final['bar_time'].min()} to {combined_final['bar_time'].max()}")
print(f"  Duration: {(combined_final['bar_time'].max() - combined_final['bar_time'].min()).days} days")

# ============ SAMPLE DATA ============
print("\n" + "="*80)
print("SAMPLE DATA (First 10 rows)")
print("="*80)
print(combined_final.head(10).to_string(index=False))

print("\n" + "="*80)
print("SAMPLE DATA (Last 10 rows)")
print("="*80)
print(combined_final.tail(10).to_string(index=False))

# ============ QUICK STATS ============
print("\n" + "="*80)
print("QUICK STATS")
print("="*80)

print("\nPrice statistics:")
price_stats = combined_final[['perp_open','perp_high','perp_low','perp_close']].describe()
print(price_stats)

print("\nFunding rate statistics:")
funding_stats = combined_final['funding_rate'].describe()
print(funding_stats)

print("\nFunding rate percentiles:")
for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
    val = combined_final['funding_rate'].quantile(p/100)
    print(f"  {p:2d}th: {val:.6f} ({val*100:.4f}%)")

# Key thresholds for reference
print("\n" + "="*80)
print("THRESHOLD REFERENCE")
print("="*80)
print("\nFor your strategy:")
print(f"  Current SHORT threshold: 0.00012 (0.012%)")
print(f"  Current LONG threshold:  0.00003 (0.003%)")
print(f"  Baseline (neutral):      0.00010 (0.010%)")

# Count how many bars are above/below thresholds
high_funding = (combined_final['funding_rate'] >= 0.00012).sum()
low_funding = (combined_final['funding_rate'] <= 0.00003).sum()

print(f"\nBars with funding >= 0.012%: {high_funding} ({high_funding/len(combined_final)*100:.1f}%)")
print(f"Bars with funding <= 0.003%: {low_funding} ({low_funding/len(combined_final)*100:.1f}%)")

# Estimate potential signals (very rough)
funding_fresh = combined_final['funding_changed'].sum()
print(f"\nTotal funding updates: {funding_fresh}")
print(f"  Potential SHORT signals: ~{int(high_funding / (len(combined_final) / funding_fresh))}")
print(f"  Potential LONG signals: ~{int(low_funding / (len(combined_final) / funding_fresh))}")
print("  (Rough estimate - actual signals need price confirmation too)")

# ============ READY FOR BACKTESTING ============
print("\n" + "="*80)
print("✅ READY FOR BACKTESTING!")
print("="*80)
print("\nNext steps:")
print("1. Update 'validation_with_ohlc.py':")
print(f"   - Set CSV_PATH = '{OUTPUT_FILE}'")
print("   - Column names already match (perp_open, perp_high, etc.)")
print("2. Run: python validation_with_ohlc.py")
print("3. Check your Profit Factor")
print("4. Follow the decision tree!")
print("\n🚀 Good luck! This is your moment of truth!")
print("="*80)
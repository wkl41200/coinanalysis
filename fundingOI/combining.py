import pandas as pd


funding = pd.read_csv('/Users/duncanwan/Desktop/learning/Bitcoin/Idea_data/funding_daily.csv')
spot = pd.read_csv('/Users/duncanwan/Desktop/learning/Bitcoin/Clean_data/btcspot_agg.csv')
future = pd.read_csv('/Users/duncanwan/Desktop/learning/Bitcoin/Clean_data/btcfuture_agg.csv')

funding_col = ['date','funding_mean', 'daily_funding_sum','funding_last','funding_first']
spot_col = ['open_time','close','volume']
future_col = ['open_time', 'close', 'volume']

funding['date'] = (
    pd.to_datetime(funding['date'], utc=True, errors='coerce')
      .dt.floor('D')  )      

funding = funding.loc[:, funding_col]
spot    = spot.loc[:, spot_col].rename(columns={'open_time': 'date'})
future  = future.loc[:, future_col].rename(columns={'open_time': 'date'})

# align to day

for df in (funding, spot, future):
    df['date'] = (
        pd.to_datetime(df['date'], utc=True, errors='coerce')  # -> tz-aware UTC
          .dt.floor('D')                                       # align to day
    )


merged = spot.merge(future, on='date', how='outer', suffixes=('_spot','_fut')) \
             .merge(funding, on='date', how='outer')

merged = merged.sort_values('date').drop_duplicates(subset=['date'], keep='last')

merged.to_csv('fundingtesting.csv')
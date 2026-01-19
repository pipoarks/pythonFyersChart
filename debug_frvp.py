import pandas as pd
import numpy as np
from indicators.frvp import calculate_frvp, get_best_resolution
from core.data_provider import fetch_raw_ticks

def debug_frvp():
    symbol = "NSE:TCS-EQ"
    df = fetch_raw_ticks(symbol)
    if df.empty:
        print("Empty DF")
        return

    # Mock times from DB
    min_t = int(df['last_traded_time'].min())
    max_t = int(df['last_traded_time'].max())
    
    start_time = min_t + 60
    end_time = max_t - 60
    chart_tf = "1min"
    
    print(f"Start: {start_time}, End: {end_time}")
    
    res = get_best_resolution(start_time, end_time, chart_tf)
    print(f"Best Res: {res}")
    
    df["dt"] = pd.to_datetime(df["last_traded_time"], unit="s", utc=True)
    df.set_index("dt", inplace=True)
    
    ohlc = df["ltp"].resample(res).ohlc()
    vol = df["last_traded_qty"].resample(res).sum()
    resampled_df = pd.concat([ohlc, vol], axis=1).dropna()
    resampled_df.columns = ['open', 'high', 'low', 'close', 'volume']
    resampled_df.reset_index(inplace=True)
    resampled_df["time"] = (resampled_df["dt"].astype("int64") // 10**9)

    print(f"Resampled length: {len(resampled_df)}")
    
    result = calculate_frvp(
        resampled_df, start_time, end_time,
        rows_layout="NumberOfRows", row_size=20, 
        value_area_pct=70
    )
    
    if result:
        print("Success!")
        print(f"POC: {result['poc']}")
    else:
        print("Result is None")

if __name__ == "__main__":
    debug_frvp()

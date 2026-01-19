import pandas as pd
from core.data_provider import fetch_raw_ticks

def check_counts():
    symbol = "NSE:TCS-EQ"
    df = fetch_raw_ticks(symbol)
    if df.empty:
        print("No data in DB.")
        return

    df["dt"] = pd.to_datetime(df["last_traded_time"], unit="s", utc=True)
    df.set_index("dt", inplace=True)
    
    for tf in ["1min", "3min", "5min", "10min", "15min", "1h"]:
        resampled = df["ltp"].resample(tf).ohlc().dropna()
        print(f"TF {tf}: {len(resampled)} candles")

if __name__ == "__main__":
    check_counts()

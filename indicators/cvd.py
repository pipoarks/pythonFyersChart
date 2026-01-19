import pandas as pd
import numpy as np

def calculate_cvd_base(df, anchor_period='D'):
    """
    Calculates the base layer CVD candles (e.g. 1-min) from OHLCV data.
    
    Rules for Delta:
    - If Close > Open -> +Volume
    - If Close < Open -> -Volume
    - If Open = Close:
        - If Close > Prev Close -> +Volume
        - If Close < Prev Close -> -Volume
        - Else -> Inherit prev direction
    """
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    
    # Calculate Delta
    deltas = np.zeros(len(df))
    prev_close = None
    prev_direction = 1 # Default to Buy if no history
    
    for i in range(len(df)):
        o = df.iloc[i]['open']
        c = df.iloc[i]['close']
        v = df.iloc[i]['volume']
        
        direction = 0
        if o != c:
            direction = 1 if c > o else -1
        else:
            if prev_close is not None:
                if c > prev_close:
                    direction = 1
                elif c < prev_close:
                    direction = -1
                else:
                    direction = prev_direction
            else:
                direction = 1
        
        deltas[i] = v * direction
        prev_close = c
        prev_direction = direction
        
    df['delta'] = deltas
    
    # Cumulative Sum with Anchor Reset
    # Converting time to datetime for grouping
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    
    # Reset CVD at the start of each anchor period (e.g., daily)
    def calculate_running_cvd(group):
        cum_delta = group['delta'].cumsum()
        # CVD Open -> Previous candle’s CVD Close (0 for first candle)
        cvd_close = cum_delta
        cvd_open = cvd_close.shift(1).fillna(0)
        
        # CVD High/Low intrabar (for base layer, we just use Open/Close path)
        cvd_high = np.maximum(cvd_open, cvd_close)
        cvd_low = np.minimum(cvd_open, cvd_close)
        
        return pd.DataFrame({
            'cvd_o': cvd_open,
            'cvd_h': cvd_high,
            'cvd_l': cvd_low,
            'cvd_c': cvd_close
        }, index=group.index)

    # Use 'dt' to group by anchor
    cvd_df = df.groupby(df['dt'].dt.to_period(anchor_period), group_keys=False).apply(calculate_running_cvd)
    
    return pd.concat([df, cvd_df], axis=1)

def aggregate_cvd_candles(df_base, tf):
    """
    Aggregates lower-timeframe CVD candles into higher-timeframe CVD candles.
    
    Aggregation Rules:
    - HTF CVD Open -> Open of first base candle
    - HTF CVD Close -> Close of last base candle
    - HTF CVD High -> Max of all base candles' Highs
    - HTF CVD Low -> Min of all base candles' Lows
    """
    if df_base.empty:
        return pd.DataFrame()
        
    df = df_base.copy()
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('dt', inplace=True)
    
    agg_rules = {
        'cvd_o': 'first',
        'cvd_h': 'max',
        'cvd_l': 'min',
        'cvd_c': 'last',
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
        'time': 'first' # We'll fix the time after resample
    }
    
    # We filter out columns that might not exist or we don't want to aggregate here
    actual_rules = {k: v for k, v in agg_rules.items() if k in df.columns}
    
    resampled = df.resample(tf).agg(actual_rules).dropna()
    resampled.reset_index(inplace=True)
    
    # Fix time to match resample start
    resampled['time'] = (resampled['dt'].astype("int64") // 10**9)
    
    return resampled

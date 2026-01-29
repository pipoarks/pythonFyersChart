import pandas as pd
import numpy as np

def calculate_cmf(df, length=20):
    """
    Calculate Chaikin Money Flow (CMF).
    Formula:
    ad = ((2*close - low - high) / (high - low)) * volume
    cmf = sum(ad, length) / sum(volume, length)
    """
    if df.empty or len(df) < length:
        return None

    # Ensure chronological order for rolling calculations
    original_index = df.index
    is_desc = False
    
    # Detect if we need to sort
    time_col = 'time' if 'time' in df.columns else ('timestamp' if 'timestamp' in df.columns else None)
    
    if time_col and len(df) > 1:
        if df[time_col].iloc[0] > df[time_col].iloc[-1]:
            is_desc = True
            df_calc = df.sort_values(by=time_col, ascending=True)
        else:
            df_calc = df
    else:
        df_calc = df

    close = df_calc['close']
    low = df_calc['low']
    high = df_calc['high']
    volume = df_calc['volume']

    # Money Flow Multiplier
    denom = high - low
    mf_mult = np.where(denom == 0, 0, (2 * close - low - high) / denom)
    mf_vol = mf_mult * volume

    # CMF = Sum(MFV, n) / Sum(Volume, n)
    # Handle division by zero when sum_vol is 0
    sum_mf_vol = mf_vol.rolling(window=length).sum()
    sum_vol = volume.rolling(window=length).sum()
    
    # Use np.where to avoid division by zero
    cmf = np.where(sum_vol == 0, 0, sum_mf_vol / sum_vol)
    
    # Create result series with the sorted index
    cmf_series = pd.Series(cmf, index=df_calc.index)
    
    # Reset index to match original dataframe positions
    cmf_series = cmf_series.reset_index(drop=True)
    cmf_series.index = original_index
        
    return cmf_series


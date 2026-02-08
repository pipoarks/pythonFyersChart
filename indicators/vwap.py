import pandas as pd
import numpy as np

def calculate_vwap(df, anchor='D'):
    """
    Calculates Volume Weighted Average Price (VWAP) with anchor resets.
    Default anchor is 'D' (Daily).
    Typical Price = (High + Low + Close) / 3
    VWAP = sum(Typical Price * Volume) / sum(Volume)
    """
    if df.empty:
        return None
    
    df = df.copy()
    
    # Calculate Typical Price
    df['tp'] = (df['high'] + df['low'] + df['close']) / 3
    df['tpv'] = df['tp'] * df['volume']
    
    # Convert time to datetime for grouping
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    
    def calc_group_vwap(group):
        cum_tpv = group['tpv'].cumsum()
        cum_vol = group['volume'].cumsum()
        # Avoid division by zero
        return cum_tpv / cum_vol.replace(0, np.nan)
        
    # Group by anchor and calculate cumulative VWAP
    vwap = df.groupby(df['dt'].dt.to_period(anchor), group_keys=False).apply(calc_group_vwap)
    
    return vwap

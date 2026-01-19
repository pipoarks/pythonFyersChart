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

    close = df['close']
    low = df['low']
    high = df['high']
    volume = df['volume']

    # Money Flow Multiplier
    # Handle high == low to avoid division by zero
    denom = high - low
    mf_mult = np.where(denom == 0, 0, (2 * close - low - high) / denom)
    
    mf_vol = mf_mult * volume

    # CMF = Sum(MFV, n) / Sum(Volume, n)
    sum_mf_vol = mf_vol.rolling(window=length).sum()
    sum_vol = volume.rolling(window=length).sum()

    cmf = sum_mf_vol / sum_vol
    
    return cmf

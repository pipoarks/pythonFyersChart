import pandas as pd
import pandas_ta as ta

def calculate_rsi(data, window=14, sma_window=None):
    """
    Calculate RSI and optionally its SMA using pandas-ta.
    """
    if isinstance(data, pd.DataFrame):
        close_prices = data['close']
    else:
        close_prices = data
        
    rsi = ta.rsi(close_prices, length=window)
    if rsi is not None:
        import numpy as np
        rsi.iloc[:window] = np.nan
    
    rsi_sma = None
    if rsi is not None and sma_window:
        rsi_sma = ta.sma(rsi, length=sma_window)
        
    return rsi, rsi_sma

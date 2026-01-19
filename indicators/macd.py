import pandas as pd
import pandas_ta as ta

def calculate_macd(data, fast=12, slow=26, signal=9):
    """
    Calculate MACD using pandas-ta.
    Using ta.macd directly instead of extension method to ensure 
    it returns None (not original DF) on failure.
    """
    if isinstance(data, pd.DataFrame):
        close_prices = data['close']
    else:
        close_prices = data
        
    return ta.macd(close_prices, fast=fast, slow=slow, signal=signal)

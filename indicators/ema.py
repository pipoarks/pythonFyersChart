import pandas as pd
import numpy as np

def calculate_ema(df, window=20):
    """
    Calculate Exponential Moving Average (EMA)
    :param df: DataFrame with 'close' column
    :param window: Int, period for EMA
    :return: Series with EMA values
    """
    if df is None or df.empty or 'close' not in df.columns:
        return None
    
    return df['close'].ewm(span=window, adjust=False).mean()

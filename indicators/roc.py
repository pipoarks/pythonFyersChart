import pandas as pd

def calculate_roc(data, length=9, source='close'):
    """
    Calculate Rate of Change (ROC)

    Parameters:
    data : pd.DataFrame or pd.Series
        Must contain a column like 'close', 'open', etc. if DataFrame.
        If Series, uses the series directly.
    length : int
        Number of periods back (same as TradingView)
    source : str
        Column name to use as price source if data is a DataFrame.

    Returns:
    pd.Series
        ROC values
    """
    if isinstance(data, pd.DataFrame):
        price = data[source]
    else:
        price = data

    roc = 100 * (price - price.shift(length)) / price.shift(length)
    return roc

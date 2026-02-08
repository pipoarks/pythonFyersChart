import pandas as pd
import pandas_ta as ta
import numpy as np

def test_rsi(window):
    data = pd.Series(np.random.random(100))
    rsi = ta.rsi(data, length=window)
    nan_count = rsi.isna().sum()
    print(f"Window: {window}, First non-NaN index: {rsi.first_valid_index()}, NaN count: {nan_count}")
    print(f"First 5 values:\n{rsi.head(window + 5)}")

if __name__ == "__main__":
    test_rsi(14)
    print("-" * 20)
    test_rsi(20)

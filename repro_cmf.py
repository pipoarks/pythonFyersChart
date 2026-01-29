import pandas as pd
import numpy as np
import sys
import os

# Add the indicators directory to path
sys.path.append(os.path.abspath('.'))
from indicators.cmf import calculate_cmf

def test_cmf():
    # Create sample data
    data = {
        'time': range(10),
        'open': [100, 102, 101, 103, 105, 104, 106, 108, 107, 109],
        'high': [105, 106, 104, 107, 109, 108, 110, 112, 111, 113],
        'low': [98, 100, 99, 101, 103, 102, 104, 106, 105, 107],
        'close': [102, 101, 103, 105, 104, 106, 108, 107, 109, 111],
        'volume': [1000, 1200, 1100, 1300, 1500, 1400, 1600, 1800, 1700, 1900]
    }

    df_asc = pd.DataFrame(data)
    df_desc = df_asc.iloc[::-1].reset_index(drop=True)

    print("--- ASC ORDER ---")
    cmf_asc = calculate_cmf(df_asc, length=5)
    print(cmf_asc)

    print("\n--- DESC ORDER ---")
    cmf_desc = calculate_cmf(df_desc, length=5)
    print(cmf_desc)

if __name__ == "__main__":
    test_cmf()

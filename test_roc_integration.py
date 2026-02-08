import pandas as pd
import numpy as np
from core.indicator_engine import get_processed_candles

def test_roc_integration():
    # Create sample data
    data = {
        'timestamp': [1700000000 + i*60 for i in range(20)],
        'open': [100 + i for i in range(20)],
        'high': [105 + i for i in range(20)],
        'low': [95 + i for i in range(20)],
        'close': [102 + i for i in range(20)],
        'volume': [1000 for i in range(20)]
    }
    df = pd.DataFrame(data)
    
    # Test parameters
    tf = "1min"
    roc_len = 5
    
    # Process through engine
    result = get_processed_candles(df, tf=tf, roc_len=roc_len)
    
    candles = result['candles']
    df_result = pd.DataFrame(candles)
    
    print("Columns in result:", df_result.columns.tolist())
    
    if 'roc' in df_result.columns:
        print("\nROC calculation check:")
        # ROC = 100 * (current - prev) / prev
        # For index 10 (length 5), it should use index 5.
        # close[10] = 112, close[5] = 107
        # ROC = 100 * (112 - 107) / 107 = 100 * 5 / 107 = 4.672897...
        
        c10 = df_result.iloc[10]['close']
        c5 = df_result.iloc[5]['close']
        roc10 = df_result.iloc[10]['roc']
        
        expected_roc10 = 100 * (c10 - c5) / c5
        
        print(f"Index 10: Close={c10}, Close[5]={c5}, ROC={roc10}")
        print(f"Expected ROC: {expected_roc10}")
        
        if np.isclose(roc10, expected_roc10):
            print("✅ ROC calculation is correct!")
        else:
            print("❌ ROC calculation discrepancy!")
    else:
        print("❌ ROC column missing in result!")

if __name__ == "__main__":
    test_roc_integration()

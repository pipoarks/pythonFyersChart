import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "candles_1min.db"
SYMBOL = "NSE:AUROPHARMA-EQ"

try:
    conn = sqlite3.connect(DB_PATH)
    # Fetch last 10 candles for the symbol
    query = f"SELECT * FROM candles WHERE symbol = '{SYMBOL}' ORDER BY timestamp DESC LIMIT 10"
    df = pd.read_sql(query, conn)
    conn.close()

    if df.empty:
        print(f"No data found for {SYMBOL}")
    else:
        print(f"Last 10 candles for {SYMBOL}:")
        print(df[['timestamp', 'close']].to_string())
        
        # Check conversion
        first_ts = df.iloc[0]['timestamp']
        print(f"\nSample Timestamp: {first_ts}")
        print(f"Readable (UTC assumption): {datetime.utcfromtimestamp(first_ts)}")
        print(f"Readable (Local/IST assumption): {datetime.fromtimestamp(first_ts)}")
        
        today_start_ts = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        print(f"\nSystem 'Today Start' Timestamp: {today_start_ts}")
        
except Exception as e:
    print(f"Error: {e}")

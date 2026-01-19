import sqlite3
import pandas as pd

# DB_PATH = r"E:\python fyers websocket\RESTDB\ticksREST.db"
DB_PATH = r"E:\python fyers websocket\ticks.db"

def fetch_raw_ticks(symbol, limit=None):
    """
    Pure database logic: Fetches raw ticks from SQLite.
    """
    conn = sqlite3.connect(DB_PATH)
    
    query = "SELECT ltp, last_traded_time, last_traded_qty FROM ticks WHERE symbol = ? ORDER BY last_traded_time"
    if limit:
        query += f" LIMIT {limit}"
        
    df = pd.read_sql(query, conn, params=(symbol,))
    conn.close()
    
    return df

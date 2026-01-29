import sqlite3
import pandas as pd
import os

# Define the absolute path to the candles database
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANDLE_DB_PATH = os.path.join(BASE_DIR, "candles_1min.db")

def fetch_1min_candles(symbol, limit=None, order="ASC"):
    """
    Fetches 1-minute candles from the candles_1min.db SQLite database.
    
    Args:
        symbol (str): The symbol to fetch candles for (e.g., 'NSE:NIFTY50-INDEX').
        limit (int, optional): The maximum number of candles to fetch.
        order (str): "ASC" for oldest first, "DESC" for latest first.
        
    Returns:
        pd.DataFrame: A DataFrame containing the candle data.
    """
    try:
        conn = sqlite3.connect(CANDLE_DB_PATH)
        
        # Base query to fetch all relevant columns
        query = """
            SELECT 
                timestamp, 
                open, 
                high, 
                low, 
                close, 
                volume, 
                tick_count 
            FROM candles 
            WHERE symbol = ? 
        """
        
        if order == "DESC":
            query += " ORDER BY timestamp DESC"
        else:
            query += " ORDER BY timestamp ASC"
            
        if limit is not None:
            query += f" LIMIT {limit}"
            
        df = pd.read_sql(query, conn, params=(symbol,))
        conn.close()
        
        if order == "DESC":
            # Return in chronological order even if we fetched the latest N
            df = df.sort_values("timestamp").reset_index(drop=True)
        
        # Ensure timestamp is treated as a datetime object if needed, 
        # but usually, we keep it as integer for internal processing 
        # and convert at the display layer. 
        # If the timestamp is in seconds, you can use:
        # df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        
        return df
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        return pd.DataFrame() # Return empty DataFrame on error
    except Exception as e:
        print(f"An error occurred: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    # Quick test if run directly
    test_symbol = "NSE:TCS-EQ"
    print(f"Testing fetch_1min_candles for {test_symbol}...")
    candles_df = fetch_1min_candles(test_symbol, limit=5)
    if not candles_df.empty:
        print(candles_df)
    else:
        print("No data found or database connection failed.")

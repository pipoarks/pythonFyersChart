from fyers_apiv3.FyersWebsocket import order_ws
from fyers_apiv3 import fyersModel
import json
import sqlite3
import time
import threading
import requests
from datetime import datetime
from core.candle_data_provider import fetch_1min_candles
from core.indicator_engine import get_processed_candles
import os
import logging

# ==========================================
# LOGGING CONFIGURATION
# ==========================================
os.makedirs('logs', exist_ok=True)
date_str = datetime.now().strftime('%Y-%m-%d')
exit_log_file = f'logs/exit_alerts_{date_str}.log'

exit_logger = logging.getLogger('ExitLogger')
exit_logger.setLevel(logging.INFO)
exit_logger.propagate = False

# File Handler
fh = logging.FileHandler(exit_log_file, encoding='utf-8')
fh.setFormatter(logging.Formatter('%(asctime)s [EXIT] %(message)s'))
exit_logger.addHandler(fh)

# Removed StreamHandler to separate console print logic from file logging
# to strictly preserve "console output as it" behavior + logs.

# ==========================================
# CONFIG & DATABASE INITIALIZATION
# ==========================================
# access_token = "E3D5D0NFAV:eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiZDoxIiwiZDoyIiwieDowIiwieDoxIiwieDoyIl0sImF0X2hhc2giOiJnQUFBQUFCcGdzQlFFVWpFaF82VjZNbFdVM3h2Mm1oS2VLVUZFX3VGenFxTEZOTEtlbjlCMDN1Wi1KeE9OUy1lT2RublluZWlFVXlBOF9aZXRGeGJMR3Flam5QLXZBdWh3bURWbU9meVkyT0tLdkpqdkVCc2FhVT0iLCJkaXNwbGF5X25hbWUiOiIiLCJvbXMiOiJLMSIsImhzbV9rZXkiOiIwZDQyZDFlM2UxMzhiMWQxMTMzZmRlNjFjNjhhZmQ0ZTRjODZiNTkwMzk3YzIxYjA5MDE1NjIzOSIsImlzRGRwaUVuYWJsZWQiOiJOIiwiaXNNdGZFbmFibGVkIjoiTiIsImZ5X2lkIjoiWUE0NDA3NyIsImFwcFR5cGUiOjEwMCwiZXhwIjoxNzcwMjUxNDAwLCJpYXQiOjE3NzAxNzY1OTIsImlzcyI6ImFwaS5meWVycy5pbiIsIm5iZiI6MTc3MDE3NjU5Miwic3ViIjoiYWNjZXNzX3Rva2VuIn0.MDZcBiKP_b3kf448CGFn6xhv-6bTHf10Ntsu--wq0JU"
client_id = "E3D5D0NFAV"

def get_access_token():
    file_path = "D:\\FyersAccesstoken.txt"
    try:
        with open(file_path, "r") as f:
            token = f.read().strip()
            print(f"✅ Loaded access token from {file_path}")
            return token
    except Exception as e:
        print(f"❌ Error reading access token from {file_path}: {e}")
        # Return a placeholder or raise error to prevent connection failure loops if critical
        return ""

# Fetch access token from file
# Fetch access token from file
accesstoken = get_access_token()
access_token = f"E3D5D0NFAV-100:{accesstoken}"




# Initialize Fyers Model for order placement
fyers_api = fyersModel.FyersModel(client_id=client_id, token=access_token, is_async=False, log_path="")

DB_PATH = "active_positions.db"

def init_db():
    # Added timeout to prevent locking on startup
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        # Enable WAL mode for concurrent write support
        conn.execute("PRAGMA journal_mode=WAL")
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                side TEXT,
                qty INTEGER,
                entry_time TEXT,
                is_squared_off INTEGER DEFAULT 0,
                order_id TEXT
            )
        """)
        # Check if order_id column exists (for existing DBs)
        cur.execute("PRAGMA table_info(positions)")
        columns = [col[1] for col in cur.fetchall()]
        if "order_id" not in columns:
            cur.execute("ALTER TABLE positions ADD COLUMN order_id TEXT")
            print("✅ Added 'order_id' column to positions table.")
        conn.commit()

init_db()

def get_ist_time():
    """Returns current IST time as a string."""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def exit_position(symbol, side, qty, order_id):
    """Squares off the position using the Fyers positions DELETE API."""
    url = "https://api-t1.fyers.in/api/v3/orders/sync"
    headers = {
        "Authorization": f"{access_token}",
        "Content-Type": "application/json"
    }
    
    # Square off ID format: symbol-productType (e.g., NSE:INDIANB-EQ-INTRADAY)
    # User requested using order_id instead of constructed pos_id
    payload = {"id": order_id}
    
    ist_now = get_ist_time()
    msg = f"⚠️ [EXIT ATTEMPT] Sending Square-off request for {symbol} | Side: {side} | Qty: {qty} | Order ID: {order_id}"
    print(f"[{ist_now}] {msg}")
    exit_logger.info(msg)
    
    try:
        # Use DELETE request as per Fyers API for squaring off positions
        response = requests.delete(url, headers=headers, json=payload)
        res_data = response.json()
        print(f"Exit Response: {res_data}")
        exit_logger.info(f"Exit Response for {symbol}: {res_data}")
        
        if res_data.get("s") == "ok":
            # Update DB flag
            with sqlite3.connect(DB_PATH, timeout=30) as conn:
                cur = conn.cursor()
                cur.execute("UPDATE positions SET is_squared_off = 1 WHERE symbol = ?", (symbol,))
                conn.commit()
            print(f"✅ DB Updated: {symbol} marked as squared off.")
            exit_logger.info(f"✅ DB Updated: {symbol} marked as squared off.")
        return res_data
    except Exception as e:
        print(f"❌ Error in exit_position: {e}")
        return None

def monitor_roc_exit():
    """Background loop to check ROC conditions for active intraday symbols at 5-minute clock intervals."""
    print(f"🚀 [{get_ist_time()}] ROC Exit Monitor Started (Triggers at 10:30, 10:35, etc.)...")
    
    last_check_minute = -1
    
    while True:
        try:
            now = datetime.now()
            # Check only at 5-minute intervals (e.g., 0, 5, 10, 15... minutes past the hour)
            if now.minute % 5 == 0 and now.minute != last_check_minute:
                last_check_minute = now.minute
                ist_now = get_ist_time()
                print(f"\n🕒 [{ist_now}] [INTERVAL START] Checking ROC for active positions...")
                
                # Fetch active positions
                with sqlite3.connect(DB_PATH, timeout=30) as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT symbol, side, qty, order_id FROM positions 
                        WHERE is_squared_off = 0
                    """)
                    active_trades = cur.fetchall()
                
                if active_trades:
                    for symbol, side, qty, order_id in active_trades:
                        # 1. Fetch 1-min candles (DESC to get LATEST)
                        df_1min = fetch_1min_candles(symbol, limit=300, order="DESC")
                        
                        if df_1min.empty:
                            print(f"⚠️ [{symbol}] No candle data found.")
                            continue
                            
                        # Filter for TODAY'S data only
                        today_start_ts = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                        df_1min = df_1min[df_1min['timestamp'] >= today_start_ts]
                        
                        if df_1min.empty:
                            print(f"ℹ️ [{symbol}] No candles for today yet.")
                            continue

                        # 2. Process for 5min ROC
                        processed = get_processed_candles(df_1min, tf="5min", roc_len=3)
                        if not processed or not processed.get("candles") or len(processed["candles"]) < 2:
                            print(f"ℹ️ [{symbol}] Not enough candles for 5min ROC calculation.")
                            continue
                        
                        # Check the last closed 5-min candle (fully formed)
                        candles = processed["candles"]
                        last_candle = candles[-2] # Candles[-1] is the current forming candle
                        timestamp = last_candle["time"]
                        roc_val = last_candle.get("roc")
                        
                        if roc_val is None:
                            print(f"ℹ️ [{symbol}] ROC value missing in processed data.")
                            continue
                        
                        # Preserve existing IST/Time logic
                        ist_candle_time = datetime.fromtimestamp(timestamp - 19800).strftime('%H:%M')
                        
                        # PRINT TO CONSOLE as requested: Time, Symbol, ROC
                        print(f"📊 [{ist_now}] [MONITOR] {symbol} ({side}) | ROC: {roc_val:.4f} @ {ist_candle_time}")

                        # 3. Check Exit Criteria
                        if side == "LONG" and roc_val <= 0:
                            trigger_msg = f"🚨 [EXIT TRIGGER] {symbol} (LONG) | ROC: {roc_val:.4f} <= 0 | Candle Time: {ist_candle_time}"
                            print(f"[{ist_now}] {trigger_msg}")
                            exit_logger.info(trigger_msg)
                            exit_position(symbol, side, qty, order_id)
                        elif side == "SHORT" and roc_val >= 0:
                            trigger_msg = f"🚨 [EXIT TRIGGER] {symbol} (SHORT) | ROC: {roc_val:.4f} >= 0 | Candle Time: {ist_candle_time}"
                            print(f"[{ist_now}] {trigger_msg}")
                            exit_logger.info(trigger_msg)
                            exit_position(symbol, side, qty, order_id)
                    
                    print(f"✅ [{ist_now}] [INTERVAL DONE] ROC check completed for all symbols.\n")
                else:
                    print(f"ℹ️ [{ist_now}] No active positions found in database.")
                    
        except Exception as e:
            print(f"❌ Error in ROC Monitor: {e}")
            
        time.sleep(10) # Poll every 10 seconds to catch the 5-min mark accurately

# Start background monitor
threading.Thread(target=monitor_roc_exit, daemon=True).start()

def onPosition(message):
    """
    Callback function to handle incoming messages from the FyersDataSocket WebSocket.
    Syncs live positions with the local SQLite database.
    """
    try:
        if isinstance(message, str):
            message = json.loads(message)
            print("Position Response:", message)
    except Exception:
        pass

    # print("Position Response:", message)

    positions = None
    for key in ("positions", "data", "position", "payload"):
        if isinstance(message, dict) and key in message:
            positions = message.get(key)
            break

    if positions is None:
        return

    def _process_pos(pos):
        symbol = pos.get("symbol") or pos.get("tradingsymbol") or pos.get("fyToken") or pos.get("s")
        netQty = pos.get("netQty", pos.get("net_qty", pos.get("qty", 0))) or 0
        buyQty = pos.get("buyQty", 0) or 0
        sellQty = pos.get("sellQty", 0) or 0

        if netQty > 0 or (buyQty > 0 and sellQty == 0):
            side = "LONG"
            qty = netQty if netQty else buyQty
        elif netQty < 0 or (sellQty > 0 and buyQty == 0):
            side = "SHORT"
            qty = abs(netQty) if netQty else sellQty
        else:
            side = "FLAT"
            qty = 0

        return {"symbol": symbol, "side": side, "qty": qty}

    if isinstance(positions, dict):
        pos_list = [positions]
    elif isinstance(positions, list):
        pos_list = positions
    else:
        pos_list = []

    ist_now = get_ist_time()
    try:
        with sqlite3.connect(DB_PATH, timeout=30) as conn:
            cur = conn.cursor()
            for p in pos_list:
                try:
                    info = _process_pos(p)
                    symbol = info["symbol"]
                    side = info["side"]
                    qty = info["qty"]

                    if side != "FLAT" and qty > 0:
                        # Upsert into DB: ONLY update side and qty. 
                        # NEVER touch order_id here, as it's handled by onOrder.
                        print(f"[{ist_now}] [DB ATTEMPT] Syncing Position -> Symbol: {symbol}, Side: {side}, Qty: {qty}")
                        cur.execute("""
                            INSERT INTO positions (symbol, side, qty, entry_time, is_squared_off)
                            VALUES (?, ?, ?, ?, 0)
                            ON CONFLICT(symbol) DO UPDATE SET
                                side = excluded.side,
                                qty = excluded.qty,
                                entry_time = COALESCE(positions.entry_time, excluded.entry_time),
                                is_squared_off = 0
                            WHERE is_squared_off = 1 OR side IS NULL OR side != excluded.side OR qty != excluded.qty
                        """, (symbol, side, qty, ist_now))
                    else:
                        # Position closed manually or outside this script
                        cur.execute("UPDATE positions SET is_squared_off = 1 WHERE symbol = ?", (symbol,))
                        
                except Exception as e:
                    print(f"Error syncing position for {p.get('symbol')}: {e}")
            conn.commit()
    except Exception as db_e:
        print(f"❌ Database error in onPosition: {db_e}")

def onclose(message):
    """
    Callback function to handle WebSocket connection close events.
    """
    print("Connection closed:", message)

def onOrder(message):
    """
    Callback function to handle incoming messages from the FyersDataSocket WebSocket.
    Extracts the order ID for the symbol and stores it in the database.
    """
    print("Order Response:", message)
    try:
        if isinstance(message, str):
            message = json.loads(message)
            
        orders_data = message.get("orders")
        if not orders_data:
            return

        # Handle both single order object and list of orders
        if isinstance(orders_data, dict):
            orders_list = [orders_data]
        elif isinstance(orders_data, list):
            orders_list = orders_data
        else:
            return

        with sqlite3.connect(DB_PATH, timeout=30) as conn:
            cur = conn.cursor()
            for order in orders_list:
                symbol = order.get("symbol")
                order_id = order.get("id")
                status = order.get("status")
                
                # We only track Active (4/6) or Filled (2) orders
                if symbol and order_id and status in [2, 4, 6]:
                    ist_now = get_ist_time()
                    # Using UPSERT logic: If it doesn't exist, create with ID.
                    # If it exists, only update the order_id.
                    print(f"[{ist_now}] [DB ATTEMPT] Syncing Order -> Symbol: {symbol}, Order ID: {order_id}")
                    cur.execute("""
                        INSERT INTO positions (symbol, order_id, entry_time, is_squared_off)
                        VALUES (?, ?, ?, 0)
                        ON CONFLICT(symbol) DO UPDATE SET
                            order_id = excluded.order_id,
                            is_squared_off = 0
                        WHERE is_squared_off = 1 OR order_id IS NULL OR order_id != excluded.order_id
                    """, (symbol, order_id, ist_now))
                    
                    if cur.rowcount > 0:
                        print(f"✅ [ORDER SYNC] Saved Order ID for {symbol}: {order_id} (Status: {status})")

            conn.commit()
    except Exception as e:
        print(f"❌ Error in onOrder sync: {e}")

def onopen():
    """
    Callback function to subscribe to data type and symbols upon WebSocket connection.
    Using separate calls to ensure both are registered successfully.
    """
    fyers.subscribe(data_type="OnPositions")
    fyers.subscribe(data_type="OnOrders")
    fyers.keep_running()


def onerror(message):
    """
    Callback function to handle WebSocket errors.

    Parameters:
        message (dict): The error message received from the WebSocket.

    """
    print("Error:", message)

# access_token is already defined at the top
fyers = order_ws.FyersOrderSocket(
    access_token=access_token,
    write_to_file=False,
    log_path="",
    on_connect=onopen,
    on_close=onclose,
    on_error=onerror,
    on_positions=onPosition,
    on_orders=onOrder  
)

if __name__ == "__main__":
    fyers.connect()





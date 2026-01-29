from fyers_apiv3.FyersWebsocket import data_ws
import pandas as pd
import json
import time
import sqlite3
from datetime import datetime

# Database connection for 1-minute candles only
conn_candles = sqlite3.connect("candles_1min.db", check_same_thread=False)
cur_candles = conn_candles.cursor()

# Buffers
# candle_data: { symbol: [ {price, qty, vtt} ] }
candle_data = {}
# last_processed_minute: { symbol: minute_timestamp }
last_processed_minute = {}
# last_vtt: { symbol: last_vol_traded_today_of_previous_minute }
last_vtt = {}

def process_tick(msg):
    symbol = msg.get("symbol")
    ltp = msg.get("ltp")
    exch_time = msg.get("exch_feed_time")
    qty = msg.get("last_traded_qty", 0)
    vtt = msg.get("vol_traded_today", 0)

    if ltp is None or symbol is None or exch_time is None:
        return

    # Determine the minute start timestamp
    minute_timestamp = (exch_time // 60) * 60
    
    if symbol not in last_processed_minute:
        last_processed_minute[symbol] = minute_timestamp
        candle_data[symbol] = []

    # If the minute has changed, finalize the previous minute's candle
    if minute_timestamp > last_processed_minute[symbol]:
        finalize_minute(symbol, last_processed_minute[symbol])
        last_processed_minute[symbol] = minute_timestamp
        candle_data[symbol] = []

    # Collect tick for OHLCV
    candle_data[symbol].append({
        'price': ltp, 
        'qty': qty,
        'vtt': vtt
    })

def finalize_minute(symbol, timestamp):
    # Finalize Candle
    ticks = candle_data.get(symbol, [])
    if ticks:
        o = ticks[0]['price']
        h = max(t['price'] for t in ticks)
        l = min(t['price'] for t in ticks)
        c = ticks[-1]['price']
        
        # Accurate Volume Calculation using vol_traded_today delta
        current_minute_end_vtt = ticks[-1]['vtt']
        
        if symbol in last_vtt:
            # Volume is the difference between this minute's last VTT and previous minute's last VTT
            v = current_minute_end_vtt - last_vtt[symbol]
        else:
            # First minute observed for this symbol: 
            # Use delta between last tick's VTT and the volume before the first tick of this minute
            v = current_minute_end_vtt - (ticks[0]['vtt'] - ticks[0]['qty'])
        
        last_vtt[symbol] = current_minute_end_vtt
        tick_count = len(ticks)

        try:
            cur_candles.execute("""
            INSERT OR IGNORE INTO candles (symbol, timestamp, open, high, low, close, volume, tick_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (symbol, timestamp, o, h, l, c, v, tick_count))
            conn_candles.commit()
            print(f"🕯️ CANDLE → {symbol} @ {datetime.fromtimestamp(timestamp).strftime('%H:%M')} | O: {o} H: {h} L: {l} C: {c} V: {v} (Ticks: {tick_count})")
        except Exception as e:
            print(f"Error saving candle for {symbol}: {e}")

def onmessage(msg):
    # System messages
    if msg.get("type") in ["ful", "sub"]:
        return

    # Tick messages
    if msg.get("type") == "sf":
        process_tick(msg)

def onopen():
    print("Connection opened")
    data_type = "SymbolUpdate"
    try:
        with open("symbols.json", "r") as f:
            symbols_data = json.load(f)
            symbols = [s["symbol"] for s in symbols_data]
    except Exception as e:
        print(f"Error loading symbols.json: {e}")
        symbols = ['NSE:SBIN-EQ', 'NSE:INFY-EQ','NSE:RELIANCE-EQ', 'NSE:TCS-EQ','NSE:HDFCBANK-EQ']
    
    print(f"Subscribing to: {symbols}")
    fyers.subscribe(symbols=symbols, data_type=data_type)
    fyers.keep_running()

def onerror(message):
    print("Error:", message)

def onclose(message):
    print("Connection closed:", message)

# Replace with actual token
access_token = "E3D5D0NFAV-100:eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiZDoxIiwiZDoyIiwieDowIiwieDoxIiwieDoyIl0sImF0X2hhc2giOiJnQUFBQUFCcGV0aVBRVEc0YWQxZFlSSjhPcnZqNGZsRnFsRlpENFpWX0R4T1RncjI1dE11aWNtSFpTcmd5Y2QzbllKcDlIdVlKX0M5dkkwOWFfbENHeXJuZi04X2tqQ2tXODVpN0hpZ2JERUtmcG04OWcyZmlvcz0iLCJkaXNwbGF5X25hbWUiOiIiLCJvbXMiOiJLMSIsImhzbV9rZXkiOiJlM2VlNThiMzBhYWVhMjdmYzE0MmY1YTQ2Zjc1NGM4OWQ2MGFmZmVhNTBjZWI2YzEwNWJmNDFhOCIsImlzRGRwaUVuYWJsZWQiOiJOIiwiaXNNdGZFbmFibGVkIjoiTiIsImZ5X2lkIjoiWUE0NDA3NyIsImFwcFR5cGUiOjEwMCwiZXhwIjoxNzY5NzMzMDAwLCJpYXQiOjE3Njk2NTg1MTEsImlzcyI6ImFwaS5meWVycy5pbiIsIm5iZiI6MTc2OTY1ODUxMSwic3ViIjoiYWNjZXNzX3Rva2VuIn0.KPLpVpkrZmyn0ezYYJ5upgHXd317f0F0Uipcc5KjeCQ"

fyers = data_ws.FyersDataSocket(
    access_token=access_token,
    write_to_file=False,
    log_path="",
    reconnect=True,
    on_connect=onopen,
    on_close=onclose,
    on_error=onerror,
    on_message=onmessage
)

if __name__ == "__main__":
    # Ensure candle DB is initialized
    import init_candle_db
    init_candle_db.init_db()
    
    try:
        fyers.connect()
    except KeyboardInterrupt:
        print("Stopping...")
        # Finalize any pending candles before exit
        for symbol, timestamp in last_processed_minute.items():
            finalize_minute(symbol, timestamp)
        fyers.close_connection()

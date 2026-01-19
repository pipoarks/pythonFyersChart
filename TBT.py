from fyers_apiv3.FyersWebsocket import data_ws
import pandas as pd
import json

import time
import sqlite3

conn = sqlite3.connect("ticks.db", check_same_thread=False)
cur = conn.cursor()

buffer = []

def save_tick_buffered(msg):
    row = (
        msg.get("symbol"),
        msg.get("ltp"),
        msg.get("last_traded_time"),
        msg.get("exch_feed_time"),
        msg.get("last_traded_qty"),
        msg.get("bid_price"),
        msg.get("ask_price"),
        msg.get("bid_size"),
        msg.get("ask_size"),
        msg.get("vol_traded_today"),
        msg.get("tot_buy_qty"),
        msg.get("tot_sell_qty"),
        msg.get("avg_trade_price"),
        msg.get("open_price"),
        msg.get("high_price"),
        msg.get("low_price"),
        msg.get("prev_close_price"),
        msg.get("ch"),
        msg.get("chp"),
        int(time.time())
    )

    buffer.append(row)

    if len(buffer) >= 5:   # commit every 100 ticks
        cur.executemany("""
        INSERT INTO ticks (
            symbol, ltp, last_traded_time, exch_feed_time,
            last_traded_qty, bid_price, ask_price,
            bid_size, ask_size, vol_traded_today,
            tot_buy_qty, tot_sell_qty,
            avg_trade_price, open_price, high_price, low_price,
            prev_close_price, ch, chp, recv_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, buffer)

        conn.commit()
        buffer.clear()





def onmessage(msg):
    print("Message received:", msg)

    # System messages
    if msg.get("type") in ["ful", "sub"]:
        return

    # Tick messages
    if msg.get("type") == "sf":
        ltp = msg["ltp"]
        symbol = msg["symbol"]
        print(f"TICK → {symbol} @ {ltp}")

        # store in DB    
        save_tick_buffered(msg)



def onopen():
    """
    Callback function to subscribe to data type and symbols upon WebSocket connection.

    """
    print("Connection opened")

    data_type = "SymbolUpdate"  # Specify the data type to subscribe to

    # Subscribe to the specified symbols and data type
    try:
        with open("symbols.json", "r") as f:
            symbols_data = json.load(f)
            symbols = [s["symbol"] for s in symbols_data]
    except Exception as e:
        print(f"Error loading symbols.json: {e}")
        symbols = ['NSE:SBIN-EQ', 'NSE:INFY-EQ','NSE:RELIANCE-EQ', 'NSE:TCS-EQ','NSE:HDFCBANK-EQ']
    
    print(f"Subscribing to: {symbols}")
    fyers.subscribe(symbols=symbols, data_type=data_type)
    
    # Keep the socket running to receive real-time data
    fyers.keep_running()

def on_depth_update(ticker, message):
    """
    Callback function to handle incoming messages from the FyersDataSocket WebSocket.

    Parameters:
        ticker (str): The ticker symbol of the received message.
        message (Depth): The received message from the WebSocket.

    """
    print("ticker", ticker)
    print("depth response:", message)
    print("total buy qty:", message.tbq)
    print("total sell qty:", message.tsq)
    print("bids:", message.bidprice)
    print("asks:", message.askprice)
    print("bidqty:", message.bidqty)
    print("askqty:", message.askqty)
    print("bids ord numbers:", message.bidordn)
    print("asks ord numbers:", message.askordn)
    print("issnapshot:", message.snapshot)
    print("tick timestamp:", message.timestamp)


def onerror(message):
    """
    Callback function to handle WebSocket errors.

    Parameters:
        message (dict): The error message received from the WebSocket.

    """
    print("Error:", message)


def onclose(message):
    """
    Callback function to handle WebSocket connection close events.
    """
    print("Connection closed:", message)

def onerror_message(message):
    """
    Callback function for error message events from the server

    Parameters:
        message (dict): The error message received from the Server.

    """
    print("Error Message:", message)

# Replace the sample access token with your actual access token obtained from Fyers
access_token = "E3D5D0NFAV-100:eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiZDoxIiwiZDoyIiwieDowIiwieDoxIiwieDoyIl0sImF0X2hhc2giOiJnQUFBQUFCcGJjUkNxcThjeF9odExzaHBDeDhvaWstVnVJQnFGYWZMRXl4ZGFuYy1PT0xmdkVhVWU1WVRxTEtHdmZGTHY1SVhQMDZFOVYtOENEMmszekhnZDhIZktwVlBLdV9zaXY0RTg4a1RXOWFaSVJiQy1KND0iLCJkaXNwbGF5X25hbWUiOiIiLCJvbXMiOiJLMSIsImhzbV9rZXkiOiJjNzdmNTg0MThmZWRiYzRmM2I4NWI1YjMyZWU0M2YxYWJkZDE1NDQ2MDM5YjhhMWM4NDAzZTI1OSIsImlzRGRwaUVuYWJsZWQiOiJOIiwiaXNNdGZFbmFibGVkIjoiTiIsImZ5X2lkIjoiWUE0NDA3NyIsImFwcFR5cGUiOjEwMCwiZXhwIjoxNzY4ODY5MDAwLCJpYXQiOjE3Njg4MDEzNDYsImlzcyI6ImFwaS5meWVycy5pbiIsIm5iZiI6MTc2ODgwMTM0Niwic3ViIjoiYWNjZXNzX3Rva2VuIn0.YhDZO839yjvxLuzbJxl35SyRVlUBj28UK-_hdXGxIpc"


fyers = data_ws.FyersDataSocket(
    access_token=access_token,  # Your access token for authenticating with the Fyers API.
    write_to_file=False,        # A boolean flag indicating whether to write data to a log file or not.
    log_path="",                # The path to the log file if write_to_file is set to True (empty string means current directory).
    reconnect=True,
    on_connect=onopen,          # Callback function to be executed upon successful WebSocket connection.
    on_close=onclose,           # Callback function to be executed when the WebSocket connection is closed.
    on_error=onerror,
    on_message=onmessage         # Callback function to handle server-related erros from the WebSocket.
)
# Establish a connection to the Fyers WebSocket
try:
    fyers.connect()
except KeyboardInterrupt:
    print("Stopping...")
    fyers.close_connection()
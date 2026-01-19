from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os

# Import our new core modules
from core.data_provider import fetch_raw_ticks
from core.indicator_engine import get_processed_candles
from indicators.frvp import calculate_frvp, get_best_resolution
import pandas as pd
import numpy as np

app = Flask(__name__)
CORS(app)

SYMBOLS_PATH = r"E:\python fyers websocket\symbols.json"

@app.route("/symbols")
def get_symbols_list():
    if os.path.exists(SYMBOLS_PATH):
        with open(SYMBOLS_PATH, "r") as f:
            return jsonify(json.load(f))
    return jsonify([])

@app.route("/config")
def get_config():
    config_path = "config.json"
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return jsonify(json.load(f))
    return jsonify({})

@app.route("/candles")
def candles():
    symbol = request.args.get("symbol")
    tf = request.args.get("tf", "1min")
    anchor = request.args.get("anchor", "D")
    intrabar_tf = request.args.get("intrabar_tf") 
    
    # New Indicator Settings
    rsi_len = int(request.args.get("rsi_len", 14))
    rsi_sma_len = request.args.get("rsi_sma_len")
    rsi_sma_len = int(rsi_sma_len) if rsi_sma_len and rsi_sma_len != 'null' else None
    
    macd_fast = int(request.args.get("macd_fast", 12))
    macd_slow = int(request.args.get("macd_slow", 26))
    macd_sig = int(request.args.get("macd_sig", 9))

    ema1_len = request.args.get("ema1_len")
    ema1_len = int(ema1_len) if ema1_len and ema1_len != 'null' else None
    
    ema2_len = request.args.get("ema2_len")
    ema2_len = int(ema2_len) if ema2_len and ema2_len != 'null' else None
    
    cmf_len = request.args.get("cmf_len")
    cmf_len = int(cmf_len) if cmf_len and cmf_len != 'null' else 20
    
    # 1. Fetch raw data using the Data Provider
    raw_ticks = fetch_raw_ticks(symbol)
    
    # 2. Process data (Resample + Indicators + CVD) using the Indicator Engine
    processed_data = get_processed_candles(
        raw_ticks, tf, intrabar_tf=intrabar_tf, anchor=anchor,
        rsi_len=rsi_len, rsi_sma_len=rsi_sma_len,
        macd_fast=macd_fast, macd_slow=macd_slow, macd_sig=macd_sig,
        ema1_len=ema1_len, ema2_len=ema2_len, cmf_len=cmf_len
    )
    
    return jsonify(processed_data)

@app.route("/frvp")
def frvp():
    symbol = request.args.get("symbol")
    start_time = int(request.args.get("start_time")) - 19800 # Convert IST back to UTC
    end_time = int(request.args.get("end_time")) - 19800
    chart_tf = request.args.get("chart_tf", "1min")
    
    rows_layout = request.args.get("rows_layout", "NumberOfRows")
    row_size = int(request.args.get("row_size", 24))
    value_area_pct = int(request.args.get("value_area_pct", 70))
    
    # 1. Fetch raw ticks
    df = fetch_raw_ticks(symbol)
    if df.empty:
        return jsonify(None)

    # 2. Select resolution
    res = get_best_resolution(start_time, end_time, chart_tf)
    
    # 3. Resample to selected resolution
    df["dt"] = pd.to_datetime(df["last_traded_time"], unit="s", utc=True)
    df.set_index("dt", inplace=True)
    
    ohlc = df["ltp"].resample(res).ohlc()
    vol = df["last_traded_qty"].resample(res).sum()
    resampled_df = pd.concat([ohlc, vol], axis=1).dropna()
    resampled_df.columns = ['open', 'high', 'low', 'close', 'volume']
    resampled_df.reset_index(inplace=True)
    resampled_df["time"] = (resampled_df["dt"].astype("int64") // 10**9)

    # 4. Calculate Profile
    result = calculate_frvp(
        resampled_df, start_time, end_time,
        rows_layout=rows_layout, row_size=row_size, 
        value_area_pct=value_area_pct
    )
    
    return jsonify(result)
@app.route("/ticks")
def ticks():
    symbol = request.args.get("symbol")
    
    # Fetch raw data
    df = fetch_raw_ticks(symbol, limit=5000)
    
    # Simple clean-up for the frontend line chart (UTC to IST)
    data = []
    last_time = 0
    for p, t in zip(df["ltp"], df["last_traded_time"]):
        current_time = int(t) + 19800
        if current_time <= last_time:
            continue
        data.append({"time": current_time, "value": float(p)})
        last_time = current_time

    return jsonify(data)

if __name__ == "__main__":
    app.run(port=5000, debug=True)

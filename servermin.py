from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
import pandas as pd
import numpy as np

# Import our optimized data provider and existing engine
from core.candle_data_provider import fetch_1min_candles
from core.indicator_engine import get_processed_candles
from indicators.frvp import calculate_frvp, get_best_resolution

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
    
    # 1. Fetch PRE-CALCULATED 1-min candles
    # This is much faster than fetching thousands of raw ticks
    df_candles = fetch_1min_candles(symbol)
    
    if df_candles.empty:
        return jsonify([])

    # 2. Process data using the Indicator Engine
    # The engine now automatically handles candle DataFrames
    processed_data = get_processed_candles(
        df_candles, tf, intrabar_tf=intrabar_tf, anchor=anchor,
        rsi_len=rsi_len, rsi_sma_len=rsi_sma_len,
        macd_fast=macd_fast, macd_slow=macd_slow, macd_sig=macd_sig,
        ema1_len=ema1_len, ema2_len=ema2_len, cmf_len=cmf_len
    )
    
    return jsonify(processed_data)

@app.route("/frvp")
def frvp():
    symbol = request.args.get("symbol")
    start_time = int(request.args.get("start_time")) - 19800 # UTC
    end_time = int(request.args.get("end_time")) - 19800
    chart_tf = request.args.get("chart_tf", "1min")
    
    rows_layout = request.args.get("rows_layout", "NumberOfRows")
    row_size = int(request.args.get("row_size", 24))
    value_area_pct = int(request.args.get("value_area_pct", 70))
    
    # 1. Fetch 1-min candles (sufficient for FRVP in most cases)
    df = fetch_1min_candles(symbol)
    if df.empty:
        return jsonify(None)

    # 2. Select resolution
    res = get_best_resolution(start_time, end_time, chart_tf)
    
    # 3. Resample to selected resolution
    df["dt"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    df.set_index("dt", inplace=True)
    
    # Resample from 1-min OHLC to target resolution
    resampled_df = df.resample(res).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
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
    
    # For /ticks endpoint, we still might want higher resolution, 
    # but for servermin, let's just return the last few 1-min candles as "points"
    df = fetch_1min_candles(symbol, limit=100)
    
    data = []
    for _, row in df.iterrows():
        # Convert to IST for frontend
        data.append({
            "time": int(row["timestamp"]) + 19800, 
            "value": float(row["close"])
        })

    return jsonify(data)

if __name__ == "__main__":
    # Use a different port if needed, or keep 5000 if server.py is not running
    app.run(port=5001, debug=True)

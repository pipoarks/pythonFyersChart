from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os

# Import our new core modules
# from core.data_provider import fetch_1min_candles
from core.candle_data_provider import fetch_1min_candles
from core.indicator_engine import get_processed_candles
from indicators.frvp import calculate_frvp, get_best_resolution
import pandas as pd
import numpy as np
import time

# Simple TTL Cache for processed candles
processed_cache = {} # { (symbol, tf, ...): (timestamp, data) }
CACHE_TTL = 2 # 2 seconds cache is enough for 3s refresh

# Raw data cache for database fetches
raw_data_cache = {} # { symbol: (timestamp, dataframe) }
RAW_CACHE_TTL = 5 # Cache raw ticks for 5 seconds

app = Flask(__name__)
CORS(app)

SYMBOLS_PATH = r"E:\python fyers websocket\symbols.json"

@app.route("/symbols")
def get_symbols_list():
    if os.path.exists(SYMBOLS_PATH):
        with open(SYMBOLS_PATH, "r") as f:
            return jsonify(json.load(f))
    return jsonify([])

@app.route("/alerted_symbols")
def get_alerted_symbols():
    import datetime, re
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    log_file = f"logs/alerts_{today_str}.log"
    symbols = set()
    
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            # Match 🚀 [ALERT TYPE] NSE:SYMBOL (TF)
            matches = re.findall(r"🚀 \[.*?\] (NSE:[\w-]+)", content)
            symbols = sorted(list(set(matches)))
            
    result = [{"symbol": sym, "name": sym.split(':')[1] if ':' in sym else sym} for sym in symbols]
    return jsonify(result)

@app.route("/watchlist")
def get_watchlist():
    config_path = "config.json"
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
            watchlist = config.get("watchlist", [])
            result = []
            for item in watchlist:
                if isinstance(item, str):
                    sym = item
                    result.append({"symbol": sym, "name": sym.split(':')[1] if ':' in sym else sym})
                else:
                    sym = item.get("symbol", "")
                    result.append({
                        "symbol": sym, 
                        "name": sym.split(':')[1] if ':' in sym else sym,
                        "alert_times": item.get("alert_times", [])
                    })
            return jsonify(result)
    return jsonify([])

@app.route("/sync_watchlist", methods=["POST"])
def sync_watchlist():
    import datetime, re
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    log_file = f"logs/alerts_{today_str}.log"
    config_path = "config.json"
    
    symbol_data = {} # {symbol: {"symbol": sym, "alert_times": [times]}}
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                # Match: 🚀 [BUY ALERT] NSE:TATAPOWER-EQ (5min) triggered at 11:25!
                match = re.search(r"🚀 \[.*?\] (NSE:[\w-]+-EQ) \(.*?\) triggered at (\d{2}:\d{2})", line)
                if match:
                    sym = match.group(1)
                    time_str = match.group(2)
                    if sym not in symbol_data:
                        symbol_data[sym] = {"symbol": sym, "alert_times": []}
                    if time_str not in symbol_data[sym]["alert_times"]:
                        symbol_data[sym]["alert_times"].append(time_str)
    
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
        
        # Sort by symbol for consistency
        watchlist_objs = [symbol_data[s] for s in sorted(symbol_data.keys())]
        config["watchlist"] = watchlist_objs
        
        with open(config_path, "w") as f:
            json.dump(config, f, indent=4)
            
        return jsonify({"success": True, "count": len(watchlist_objs), "symbols": watchlist_objs})
    
    return jsonify({"success": False, "error": "config.json not found"})

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
    
    rsi_len = request.args.get("rsi_len")
    rsi_len = int(rsi_len) if rsi_len and rsi_len != 'null' else None
    rsi_sma_len = request.args.get("rsi_sma_len")
    rsi_sma_len = int(rsi_sma_len) if rsi_sma_len and rsi_sma_len != 'null' else None
    
    macd_fast = request.args.get("macd_fast")
    macd_slow = request.args.get("macd_slow")
    macd_sig = request.args.get("macd_sig")
    macd_fast = int(macd_fast) if macd_fast and macd_fast != 'null' else None
    macd_slow = int(macd_slow) if macd_slow and macd_slow != 'null' else None
    macd_sig = int(macd_sig) if macd_sig and macd_sig != 'null' else None

    ema1_len = request.args.get("ema1_len")
    ema1_len = int(ema1_len) if ema1_len and ema1_len != 'null' else None
    
    ema2_len = request.args.get("ema2_len")
    ema2_len = int(ema2_len) if ema2_len and ema2_len != 'null' else None
    
    cmf_len = request.args.get("cmf_len")
    cmf_len = int(cmf_len) if cmf_len and cmf_len != 'null' else None
    
    roc_len = request.args.get("roc_len")
    roc_len = int(roc_len) if roc_len and roc_len != 'null' else None
    
    vwap_enabled = request.args.get("vwap") == "true"
    
    fvg_threshold = float(request.args.get("fvg_threshold", 0.0))
    fvg_auto = request.args.get("fvg_auto") == "true"
    fvg_only_today = request.args.get("fvg_only_today") == "true"
    
    # Cache key
    cache_key = (symbol, tf, anchor, intrabar_tf, rsi_len, rsi_sma_len, macd_fast, macd_slow, macd_sig, ema1_len, ema2_len, cmf_len, roc_len, vwap_enabled, fvg_threshold, fvg_auto, fvg_only_today)
    
    now = time.time()
    if cache_key in processed_cache:
        timestamp, cached_data = processed_cache[cache_key]
        if now - timestamp < CACHE_TTL:
            return jsonify(cached_data)

    # 1. Fetch raw data using the Data Provider (with caching)
    if symbol in raw_data_cache:
        cached_ts, cached_df = raw_data_cache[symbol]
        if now - cached_ts < RAW_CACHE_TTL:
            raw_ticks = cached_df
        else:
            raw_ticks = fetch_1min_candles(symbol)
            raw_data_cache[symbol] = (now, raw_ticks)
    else:
        raw_ticks = fetch_1min_candles(symbol)
        raw_data_cache[symbol] = (now, raw_ticks)
    
    # 2. Process data (Resample + Indicators + CVD) using the Indicator Engine
    processed_data = get_processed_candles(
        raw_ticks, tf, intrabar_tf=intrabar_tf, anchor=anchor,
        rsi_len=rsi_len, rsi_sma_len=rsi_sma_len,
        macd_fast=macd_fast, macd_slow=macd_slow, macd_sig=macd_sig,
        ema1_len=ema1_len, ema2_len=ema2_len, cmf_len=cmf_len, roc_len=roc_len,
        show_vwap=vwap_enabled, fvg_threshold=fvg_threshold, fvg_auto=fvg_auto, fvg_only_today=fvg_only_today
    )
    
    # Update cache
    processed_cache[cache_key] = (now, processed_data)
    
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
    
    # 1. Fetch 1-min candles from candles_1min.db
    df = fetch_1min_candles(symbol)
    if df.empty:
        return jsonify(None)

    # 2. Select resolution
    res = get_best_resolution(start_time, end_time, chart_tf)
    
    # 3. Resample to selected resolution (candles already have OHLC)
    df["dt"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    df.set_index("dt", inplace=True)
    
    # Resample from 1-min candles to target resolution
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
    
    # Fetch raw data
    df = fetch_1min_candles(symbol, limit=5000)
    
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

@app.route("/fvg_report")
def fvg_report():
    symbol = request.args.get("symbol")
    tf = request.args.get("tf", "5min")
    fvg_threshold = float(request.args.get("fvg_threshold", 0.0))
    fvg_auto = request.args.get("fvg_auto") == "true"
    fvg_only_today = request.args.get("fvg_only_today") == "true"

    # 1. Fetch data
    df_1min = fetch_1min_candles(symbol)
    if df_1min.empty:
        return "No data found for symbol.", 404

    # 2. Process via engine to get aggregated candles and FVGs
    # We use get_processed_candles to ensure identical logic to the chart
    processed = get_processed_candles(
        df_1min, tf=tf, 
        fvg_threshold=fvg_threshold, fvg_auto=fvg_auto, fvg_only_today=fvg_only_today
    )
    
    fvg_records = processed.get("fvg", [])
    
    # 3. Generate Report Text
    report = []
    report.append(f"FAIR VALUE GAP (FVG) DETAILS REPORT")
    report.append(f"===================================")
    report.append(f"Symbol:    {symbol}")
    report.append(f"Timeframe: {tf}")
    report.append(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')} IST")
    report.append(f"Settings:  Threshold={fvg_threshold}%, Auto={fvg_auto}, OnlyToday={fvg_only_today}")
    report.append(f"Total gaps identified: {len(fvg_records)}")
    report.append(f"")
    
    if not fvg_records:
        report.append("No Fair Value Gaps detected with the current settings.")
    else:
        for i, fvg in enumerate(fvg_records, 1):
            t_str = pd.to_datetime(fvg['time'], unit='s').strftime('%Y-%m-%d %H:%M:%S')
            is_bull = fvg['is_bull']
            top = fvg['top']
            bottom = fvg['bottom']
            
            report.append(f"{i}. [{t_str}] {'BULLISH' if is_bull else 'BEARISH'} FVG")
            report.append(f"   Levels: Top={top:.2f}, Bottom={bottom:.2f}")
            
            if is_bull:
                report.append(f"   Why: Current Low ({top:.2f}) is higher than the High from two candles ago ({bottom:.2f}).")
                report.append(f"   How: An aggressive upwards move created a 'Fair Value Gap' where price jumped so fast that sellers couldn't match buyers in that range.")
            else:
                report.append(f"   Why: Current High ({bottom:.2f}) is lower than the Low from two candles ago ({top:.2f}).")
                report.append(f"   How: An aggressive downwards move created a 'Fair Value Gap' where price dropped so fast that buyers couldn't match sellers in that range.")
            
            if fvg['mitigated']:
                m_time = pd.to_datetime(fvg['mitigation_time'], unit='s').strftime('%Y-%m-%d %H:%M:%S')
                report.append(f"   Status: MITIGATED at {m_time}")
            else:
                report.append(f"   Status: UNMITIGATED (Open Gap)")
            
            report.append("")

    return "\n".join(report), 200, {'Content-Type': 'text/plain; charset=utf-8'}

if __name__ == "__main__":
    app.run(port=5000, debug=True, threaded=True)

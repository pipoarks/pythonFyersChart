import time
import pandas as pd
import json
from datetime import datetime, timedelta
from core.candle_data_provider import fetch_1min_candles
from core.indicator_engine import get_processed_candles
from indicators.frvp import calculate_frvp, get_best_resolution

# ==========================================
# STRATEGY ALERT CONFIGURATION
# ==========================================
# TIMEFRAME: Global timeframe for all alerts (e.g., '1min', '5min', '15min')
# price_above: Alert if candle CLOSE goes above this number
# cvd_above: Alert if CVD crosses ABOVE this value
# ==========================================

# Global timeframe setting - change this to monitor different timeframes
TIMEFRAME = '5min'

ALERT_CONFIG = [
    {
        'symbol': 'NSE:TCS-EQ',
        'tf': TIMEFRAME,  # Uses the global TIMEFRAME variable
        'price_above': 3170.0,
        'cvd_above': -10000.0
    }
    # {
    #     'symbol': 'NSE:TCS-EQ',
    #     'tf': '5min',
    #     'price_above': 3175.0,
    #     'cvd_above': 5000.0
    # }
]

# State to track alerts and prevent repeated notifications for the same candle
# key: (symbol, tf, alert_type), value: last_alerted_timestamp
alert_state = {}

# Load config for FRVP default range
def load_frvp_config():
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            frvp_config = config.get('indicators', {}).get('frvp', {})
            default_range = frvp_config.get('defaultRange', {})
            return {
                'start_h': default_range.get('start', {}).get('h', 13),
                'start_m': default_range.get('start', {}).get('m', 00),
                'end_h': default_range.get('end', {}).get('h', 13),
                'end_m': default_range.get('end', {}).get('m', 30),
                'rows': frvp_config.get('rows', 24),
                'va_pct': frvp_config.get('vaPct', 70)
            }
    except:
        # Fallback defaults
        return {'start_h': 9, 'start_m': 15, 'end_h': 9, 'end_m': 30, 'rows': 24, 'va_pct': 70}

frvp_config = load_frvp_config()

def calculate_frvp_for_today(symbol, df_1min):
    """
    Calculate FRVP using the default range from config.json
    Returns: (frvp_result, resolution_used)
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Create start and end times based on config
    start_time = today.replace(hour=frvp_config['start_h'], minute=int(frvp_config['start_m']))
    end_time = today.replace(hour=frvp_config['end_h'], minute=int(frvp_config['end_m']))
    
    # Convert to UTC timestamps (subtract IST offset)
    start_timestamp = int(start_time.timestamp())
    end_timestamp = int(end_time.timestamp())
    
    # Prepare dataframe for FRVP
    df = df_1min.copy()
    df["dt"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    df.set_index("dt", inplace=True)
    
    # Auto-select resolution (matches UI behavior)
    res = get_best_resolution(start_timestamp, end_timestamp, '1min')
    
    # Resample
    resampled_df = df.resample(res).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    resampled_df.reset_index(inplace=True)
    resampled_df["time"] = (resampled_df["dt"].astype("int64") // 10**9)
    
    # Calculate FRVP
    result = calculate_frvp(
        resampled_df, start_timestamp, end_timestamp,
        row_size=frvp_config['rows'], 
        value_area_pct=frvp_config['va_pct']
    )
    
    return result, res

# Load config for CVD Reference
def load_cvd_config():
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            cvd_conf = config.get('indicators', {}).get('cvd', {})
            return {
                'refCandles': cvd_conf.get('refCandles', 4),  # Default to 4
                'anchor': cvd_conf.get('anchor', 'D')
            }
    except:
        return {'refCandles': 4, 'anchor': 'D'}

cvd_config = load_cvd_config()

def calculate_cvd_reference(df):
    """
    Calculates the CVD Reference Level (High of first N candles of the current day).
    """
    if df.empty or 'cvd_h' not in df.columns:
        return None
        
    # Filter for today's data (assuming timestamps are in seconds)
    # df has a 'dt' index or 'timestamp' column. helper creates 'dt' index usually.
    # The df from get_processed_candles has 'time' column in seconds
    
    df = df.copy()
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata') # Ensure IST for day grouping
        
    last_candle_time = df['dt'].iloc[-1]
    current_day = last_candle_time.normalize() # Midnight of the last candle's day
    
    # Get candles for that specific day
    day_data = df[df['dt'] >= current_day].copy()
    
    if day_data.empty:
        return None
        
    # Take first N candles
    n_candles = cvd_config['refCandles']
    first_n = day_data.iloc[:n_candles]
    
    if first_n.empty:
        return None
        
    # Debug: Print first N CVD candles
    # print(f"DEBUG: First {n_candles} CVD Highs: {first_n['cvd_h'].tolist()}")
    
    # Max of CVD Highs
    ref_level = first_n['cvd_h'].max()
    return ref_level

def check_alerts():
    """
    Main logic to poll data and evaluate alert conditions.
    """
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 Scanning for alerts...")
    
    for config in ALERT_CONFIG:
        symbol = config.get('symbol')
        tf = config.get('tf', '1min')
        price_threshold = config.get('price_above')
        cvd_threshold = config.get('cvd_above')
        
        # 1. Fetch recent 1-min candles
        df_1min = fetch_1min_candles(symbol, limit=300)
        if df_1min.empty:
            print(f"⚠️ No data found for {symbol}")
            continue
            
        # 2. Process data (Resampling + Indicators + CVD)
        processed_data = get_processed_candles(df_1min, tf=tf)
        if not processed_data or len(processed_data) < 2:
            continue
            
        # 3. Get latest and previous candle for analysis
        last_candle = processed_data[-1]
        prev_candle = processed_data[-2]
        
        # We explicitly use the 'close' price for the alert threshold
        current_price = last_candle['close']
        current_cvd = last_candle['cvd_c']
        prev_cvd = prev_candle['cvd_c']
        
        timestamp = last_candle['time']
        # Note: indicator_engine already converted timestamp to IST (+19800)
        # So we subtract it back to get UTC, then let fromtimestamp apply local timezone
        time_str = datetime.fromtimestamp(timestamp - 19800).strftime('%H:%M')

        # --- CONDITION 1: Price Above ---
        if price_threshold and current_price > price_threshold:
            state_key = (symbol, tf, 'price_above')
            if alert_state.get(state_key) != timestamp:
                print(f"🔔 [ALERT] {symbol} ({tf}) Price: {current_price} > {price_threshold} at {time_str}")
                print(f" [CVD is =] {symbol} ({tf}) CVD: {current_cvd:.0f} > {cvd_threshold} at {time_str}")
                alert_state[state_key] = timestamp

        # --- CONDITION 2: Cumulative CVD Above ---
        if cvd_threshold and current_cvd is not None:
            if current_cvd > cvd_threshold:
                state_key = (symbol, tf, 'cvd_above')
                if alert_state.get(state_key) != timestamp:
                    print(f"🔔 [CVD ALERT] {symbol} ({tf}) CVD: {current_cvd:.0f} > {cvd_threshold} at {time_str}")
                    alert_state[state_key] = timestamp
        
        # --- CVD Reference Level Check (High of First N Candles) ---
        cvd_ref_level = calculate_cvd_reference(pd.DataFrame(processed_data))
        if cvd_ref_level is not None:
            if current_cvd > cvd_ref_level:
                 state_key = (symbol, tf, 'cvd_ref_cross')
                 # Uncomment to enable alerts on Ref Line Cross
                 # if alert_state.get(state_key) != timestamp:
                 #    print(f"🚀 [CVD Breakout] {symbol} ({tf}) CVD: {current_cvd:.0f} > Ref Level: {cvd_ref_level:.0f}")
                 #    alert_state[state_key] = timestamp
                 pass

        # --- FRVP VALUES (Display once per scan) ---
        # Calculate FRVP for the default range
        try:
            frvp_result, frvp_resolution = calculate_frvp_for_today(symbol, df_1min)
            if frvp_result:
                # Format the time range
                start_time_str = f"{frvp_config['start_h']:02d}:{int(frvp_config['start_m']):02d}"
                end_time_str = f"{frvp_config['end_h']:02d}:{int(frvp_config['end_m']):02d}"
                
                # Format Output
                frvp_info = f"📊 [FRVP {start_time_str}-{end_time_str} @ {frvp_resolution}] {symbol} | POC: {frvp_result['poc']:.2f} | VAH: {frvp_result['vah']:.2f} | VAL: {frvp_result['val']:.2f}"
                
                # Add CVD Info
                if current_cvd is not None:
                     frvp_info += f" | CVD: {current_cvd:.0f}"
                
                if cvd_ref_level is not None:
                    frvp_info += f" | CVD Ref: {cvd_ref_level:.0f}"
                    
                print(frvp_info)
        except Exception as e:
            # Silently skip if FRVP calculation fails (e.g., no data in range)
            pass

if __name__ == "__main__":
    print("🚀 Strategy Alert Monitoring Started")
    print("Monitoring symbols from ALERT_CONFIG...")
    
    try:
        while True:
            check_alerts()
            # Sleep for a bit before checking again
            # Since we work with 1-min candles, checking every 15-30s is reasonable
            time.sleep(60) 
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped by user.")
    except Exception as e:
        print(f"❌ Fatal Error: {e}")

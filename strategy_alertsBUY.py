import os
import time
import json
import logging
import pandas as pd
from datetime import datetime, timedelta
from core.candle_data_provider import fetch_1min_candles
from core.indicator_engine import get_processed_candles
from indicators.frvp import calculate_frvp, get_best_resolution

# ==========================================
# LOGGING CONFIGURATION
# ==========================================
os.makedirs('logs', exist_ok=True)
date_str = datetime.now().strftime('%Y-%m-%d')

# 1. Total Logger (All logs)
total_log_file = f'logs/general_{date_str}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(total_log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# 2. Alert Logger (Alerts only)
alert_log_file = f'logs/alerts_{date_str}.log'
alert_logger = logging.getLogger('AlertLogger')
alert_logger.setLevel(logging.INFO)
alert_fh = logging.FileHandler(alert_log_file, encoding='utf-8')
alert_fh.setFormatter(logging.Formatter('%(asctime)s [ALERT] %(message)s'))
alert_logger.addHandler(alert_fh)

# ==========================================
# GLOBAL CONFIGURATION
# ==========================================
TIMEFRAME = "5min"

SYMBOLS = [  
"NSE:HINDZINC-EQ",   
  
"NSE:PETRONET-EQ"
]

# State to track alerts and prevent repeated notifications for the same candle
# key: (symbol, tf, alert_type), value: last_alerted_timestamp
alert_state = {}
STOPPED_SYMBOLS = set()

# ==========================================
# HELPER FUNCTIONS
# ==========================================
# ... (existing helper functions) ...

# ==========================================
# MAIN LOGIC
# ==========================================


def load_frvp_config():
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            frvp_config = config.get('indicators', {}).get('frvp', {})
            default_range = frvp_config.get('defaultRange', {})
            return {
                'start_h': default_range.get('start', {}).get('h', 9),
                'start_m': default_range.get('start', {}).get('m', 35),
                'end_h': default_range.get('end', {}).get('h', 10),
                'end_m': default_range.get('end', {}).get('m', 35),
                'rows': frvp_config.get('rows', 24),
                'va_pct': frvp_config.get('vaPct', 70)
            }
    except:
        return {'start_h': 9, 'start_m': 15, 'end_h': 9, 'end_m': 30, 'rows': 24, 'va_pct': 70}

frvp_config = load_frvp_config()

def load_cvd_config():
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            cvd_conf = config.get('indicators', {}).get('cvd', {})
            return {
                'refCandles': cvd_conf.get('refCandles', 12),  # Default to 12
                'anchor': cvd_conf.get('anchor', 'D')
            }
    except:
        return {'refCandles': 12, 'anchor': 'D'}
cvd_config = load_cvd_config()

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

def calculate_cvd_reference(df):
    """
    Calculates the CVD Reference Level (HIGH of first N candles of the current day).
    For BUY strategy, we track the highest CVD level from the first N candles.
    """
    if df.empty or 'cvd_h' not in df.columns:
        return None
        
    df = df.copy()
    
    # In processed_data (from indicator_engine), 'time' is already IST shifted (unix timestamp + 19800)
    # We should normalize based on that.
    if 'dt' not in df.columns:
        # Just convert the already shifted timestamp to a datetime for comparison
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
        
    last_candle_time = df['dt'].iloc[-1]
    current_day = last_candle_time.normalize()
    
    day_data = df[df['dt'] >= current_day].copy()
    
    if day_data.empty:
        return None
        
    n_candles = cvd_config['refCandles']
    first_n = day_data.iloc[:n_candles]
    
    if first_n.empty:
        return None
        
    ref_level = first_n['cvd_h'].max()
    return ref_level

# ==========================================
# MAIN LOGIC
# ==========================================

def check_alerts():
    active_symbols = [s for s in SYMBOLS if s not in STOPPED_SYMBOLS]
    if not active_symbols:
        logger.info("💤 All symbols alerted. Monitoring paused.")
        return

    logger.info(f"🔍 Scanning for alerts on {len(active_symbols)} symbols ({TIMEFRAME})...")
    
    for symbol in active_symbols:
        try:
            # 1. Fetch Data - LATEST 500 candles
            df_1min = fetch_1min_candles(symbol, limit=500, order="DESC")
            if df_1min.empty:
                continue

            # 2. Process Data for Monitoring Timeframe
            processed_raw = get_processed_candles(df_1min, tf=TIMEFRAME)
            if not processed_raw or not processed_raw.get('candles') or len(processed_raw['candles']) < 2:
                continue

            processed_candles = processed_raw['candles']
            last_candle = processed_candles[-2]
            timestamp = last_candle['time']
            time_str = datetime.fromtimestamp(timestamp - 19800).strftime('%H:%M')
            
            # Current Values
            current_close = last_candle['close']
            current_cvd = last_candle['cvd_c']

            # 3. Calculate Indicators (FRVP & CVD Ref)
            
            # A) FRVP
            frvp_result, frvp_res = calculate_frvp_for_today(symbol, df_1min)
            if not frvp_result:
                continue
                
            frvp_vah = frvp_result['vah'] # "Top High Node" implies Value Area High
            frvp_val = frvp_result['val'] # "Top Low Node" implies Value Area Low
            frvp_poc = frvp_result['poc']

            # B) CVD Reference
            # Note: CVD Ref should be calculated on the timeframe of monitoring or base? 
            # Usually Ref Line is "Day's first N candles". If we use processed_data (5min), refCandles=3 means first 15 mins.
            # If we used raw 1min, refCandles=3 means first 3 mins.
            # Given processed_data is passed, it uses the global TIMEFRAME (5min).
            cvd_ref_level = calculate_cvd_reference(pd.DataFrame(processed_candles))
            
            if cvd_ref_level is None:
                continue

            # 4. Check Conditions
            # Condition 1: Close Price > FRVP VAH
            cond_price = current_close > frvp_vah
            
            # Condition 2: CVD Close > CVD Ref Line
            cond_cvd = current_cvd > cvd_ref_level
            
            # Print Logic (Always print status or only on alert?)
            # "When the condition is met, trigger an alert and print all indicator values"
            
            if cond_price and cond_cvd:
                state_key = (symbol, TIMEFRAME, 'buy_strategy')
                
                # Check if this candle was already alerted
                if alert_state.get(state_key) != timestamp:
                    alert_logger.info(f"🚀 [BUY ALERT] {symbol} ({TIMEFRAME}) triggered at {time_str}!")
                    alert_logger.info(f"    ✅ Price: {current_close:.2f} > FRVP VAH: {frvp_vah:.2f}")
                    alert_logger.info(f"    ✅ CVD:   {current_cvd:.0f} > CVD Ref:  {cvd_ref_level:.0f}")
                    alert_state[state_key] = timestamp
                    STOPPED_SYMBOLS.add(symbol)
            else:
                # Debug line to see why it didn't trigger
                reason = []
                if not cond_price: reason.append(f"Price {current_close:.2f} <= VAH {frvp_vah:.2f}")
                if not cond_cvd: reason.append(f"CVD {current_cvd:.0f} <= Ref {cvd_ref_level:.0f}")
                # Optional: log reason only if one condition is met
                # if cond_price or cond_cvd:
                #    logger.info(f"    {symbol} | Skipping alert: {', '.join(reason)}")

            # Optional: Print status for debugging/monitoring even if no alert
            logger.info(f"    {symbol} | CVD={current_cvd:.0f} vs Ref={cvd_ref_level:.0f} | Close={current_close:.2f} vs VAH={frvp_vah:.2f}")

            
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            continue

def print_startup_summary():
    logger.info("="*50)
    logger.info(f"🚀 INITIALIZING STRATEGY ALERTS ({TIMEFRAME})")
    logger.info("="*50)
    logger.info(f"📅 FRVP Configuration:")
    logger.info(f"   • Range: {int(frvp_config['start_h']):02d}:{int(frvp_config['start_m']):02d} - {int(frvp_config['end_h']):02d}:{int(frvp_config['end_m']):02d}")
    logger.info(f"   • Rows: {frvp_config['rows']} | VA%: {frvp_config['va_pct']}")
    
    logger.info(f"\n🌊 CVD Configuration:")
    logger.info(f"   • Anchor: {cvd_config['anchor']}")
    logger.info(f"   • Ref Candles: First {cvd_config['refCandles']} candles of the day")
    logger.info("-" * 50)
    logger.info("⏳ calculating reference levels for all symbols...")
    
    for symbol in SYMBOLS:
        try:
            # Fetch just enough data to calculate references - LATEST
            df_1min = fetch_1min_candles(symbol, limit=300, order="DESC")
            if df_1min.empty:
                logger.info(f"❌ {symbol}: No Data Available")
                continue
                
            processed_raw = get_processed_candles(df_1min, tf=TIMEFRAME)
            if not processed_raw or not processed_raw.get('candles'):
                logger.info(f"❌ {symbol}: Insufficient Data for {TIMEFRAME}")
                continue
            
            processed_candles = processed_raw['candles']
                
            # Calculate CVD Ref
            cvd_ref = calculate_cvd_reference(pd.DataFrame(processed_candles))
            
            # Calculate FRVP (Optional to print here, but useful)
            frvp_res, _ = calculate_frvp_for_today(symbol, df_1min)
            vah_text = f"{frvp_res['vah']:.2f}" if frvp_res else "N/A"
            
            ref_text = f"{cvd_ref:.0f}" if cvd_ref is not None else "N/A"
            
            logger.info(f"✅ {symbol:<20} | CVD Ref (1st {cvd_config['refCandles']} c): {ref_text:>6} | FRVP VAH: {vah_text:>8}")

            
        except Exception as e:
            logger.error(f"❌ {symbol}: Error ({e})")
            
    logger.info("="*50 + "\n")

if __name__ == "__main__":
    print_startup_summary()
    logger.info("🚀 Buy Alert Monitoring Started...")
    
    try:
        while True:
            check_alerts()
            time.sleep(60) 
    except KeyboardInterrupt:
        logger.info("👋  Buy Alert Monitoring stopped by user.")

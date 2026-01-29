import pandas as pd
import numpy as np
from indicators.rsi import calculate_rsi
from indicators.macd import calculate_macd
from indicators.macd import calculate_macd
from indicators.cvd import calculate_cvd_base, aggregate_cvd_candles
from indicators.ema import calculate_ema
from indicators.cmf import calculate_cmf

def get_processed_candles(df, tf="1min", intrabar_tf=None, anchor="D", rsi_len=14, rsi_sma_len=None, macd_fast=12, macd_slow=26, macd_sig=9, ema1_len=None, ema2_len=None, cmf_len=20):
    """
    Enhanced processor: Turns raw ticks OR 1-min candles into CVD Candles and OHLC Indicators.
    """
    if df.empty:
        return []

    # 1. Detect input type and Prepare base_df
    if 'timestamp' in df.columns and 'open' in df.columns:
        # Input is already Candles (from candle_data_provider)
        base_df = df.copy()
        base_df["time"] = base_df["timestamp"]
        if not intrabar_tf:
            intrabar_tf = "1min"
    else:
        # Input is Raw Ticks (from data_provider)
        # Determine Intrabar Timeframe (Rule 1)
        if not intrabar_tf:
            if 'min' in tf or 'h' in tf:
                intrabar_tf = "1min"
            elif 's' in tf:
                intrabar_tf = "1s"
            elif 'D' in tf:
                intrabar_tf = "5min"
            else:
                intrabar_tf = "1min" # Default

        # Resample into Base Intrabar layer
        df["dt_tmp"] = pd.to_datetime(df["last_traded_time"], unit="s", utc=True)
        df.set_index("dt_tmp", inplace=True)
        
        base_ohlc = df["ltp"].resample(intrabar_tf).ohlc()
        base_volume = df["last_traded_qty"].resample(intrabar_tf).sum()
        base_df = pd.concat([base_ohlc, base_volume], axis=1).dropna()
        base_df.columns = ['open', 'high', 'low', 'close', 'volume']
        base_df.reset_index(inplace=True)
        
        # Convert dt to unix time for internal functions
        base_df["time"] = (base_df["dt_tmp"].astype("int64") // 10**9)
        intrabar_tf = intrabar_tf # keep it for comparison

    # 3. Calculate Base CVD Layer (Rule 2 & 3)
    cvd_base_df = calculate_cvd_base(base_df, anchor_period=anchor)

    # 4. Aggregate to Final Chart Timeframe (Rule 4 & 5)
    if tf != intrabar_tf:
        final_df = aggregate_cvd_candles(cvd_base_df, tf)
    else:
        final_df = cvd_base_df

    # 5. Initialize Other Indicator Columns
    final_df['rsi'] = np.nan
    final_df['rsi_sma'] = np.nan
    final_df['macd'] = np.nan
    final_df['macd_h'] = np.nan
    final_df['macd_s'] = np.nan
    final_df['ema1'] = np.nan
    final_df['ema2'] = np.nan
    final_df['cmf'] = np.nan

    try:
        # Calculate RSI and MACD on the final aggregated data
        rsi_values, rsi_sma_values = calculate_rsi(final_df, window=rsi_len, sma_window=rsi_sma_len)
        if rsi_values is not None:
            final_df['rsi'] = rsi_values
        if rsi_sma_values is not None:
            final_df['rsi_sma'] = rsi_sma_values
        
        macd_data = calculate_macd(final_df, fast=macd_fast, slow=macd_slow, signal=macd_sig)
        if macd_data is not None and not macd_data.empty:
            final_df['macd'] = macd_data.iloc[:, 0]
            final_df['macd_h'] = macd_data.iloc[:, 1]
            final_df['macd_s'] = macd_data.iloc[:, 2]

        if ema1_len is not None:
             ema1_values = calculate_ema(final_df, window=ema1_len)
             if ema1_values is not None:
                 final_df['ema1'] = ema1_values
        
        if ema2_len is not None:
             ema2_values = calculate_ema(final_df, window=ema2_len)
             if ema2_values is not None:
                 final_df['ema2'] = ema2_values
         
        if cmf_len is not None:
            cmf_values = calculate_cmf(final_df, length=cmf_len)
            if cmf_values is not None:
                final_df['cmf'] = cmf_values
    except Exception as e:
        print(f"Indicator calculation warning: {e}")
    
    # 6. Handle NaNs for JSON compatibility
    final_df = final_df.replace({np.nan: None})

    # 7. Convert to IST for display
    final_df["time"] = final_df["time"] + 19800

    return final_df.to_dict("records")

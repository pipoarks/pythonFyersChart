import pandas as pd
import numpy as np

def calculate_frvp(df, start_time, end_time, 
                   rows_layout="NumberOfRows", 
                   row_size=24, 
                   volume_mode="Total", 
                   value_area_pct=70, 
                   tick_size=0.05):
    """
    Fixed Range Volume Profile Parser.
    df: Dataframe with [open, high, low, close, volume, time]
    """
    
    # 1. Filter range
    mask = (df['time'] >= start_time) & (df['time'] <= end_time)
    range_df = df.loc[mask].copy()
    
    if range_df.empty:
        return None

    profile_low = range_df['low'].min()
    profile_high = range_df['high'].max()
    
    # 2. Setup Bins
    if rows_layout == "TicksPerRow":
        ticks_per_row = row_size
    else: # NumberOfRows
        ticks_per_row = max(1, round((profile_high - profile_low) / row_size / tick_size))
        
    bin_size = ticks_per_row * tick_size
    
    # Adjust profile boundaries to align with bins
    start_price = np.floor(profile_low / bin_size) * bin_size
    end_price = np.ceil(profile_high / bin_size) * bin_size
    
    bins = np.arange(start_price, end_price + bin_size, bin_size)
    num_bins = len(bins) - 1
    
    # Initialize profile data
    # structure: { price: float, total: float, up: float, down: float }
    profile_rows = []
    for i in range(num_bins):
        profile_rows.append({
            'price': float(bins[i]),
            'total': 0.0,
            'up': 0.0,
            'down': 0.0
        })

    # 3. Distribute Volume
    for _, candle in range_df.iterrows():
        c_low = candle['low']
        c_high = candle['high']
        c_vol = candle['volume']
        c_type = 'up' if candle['close'] > candle['open'] else 'down'
        
        # Find which bins are touched
        # Indices of bins that overlap with [c_low, c_high]
        first_bin = int(max(0, np.floor((c_low - start_price) / bin_size)))
        last_bin = int(min(num_bins - 1, np.floor((c_high - start_price) / bin_size)))
        
        bins_touched = last_bin - first_bin + 1
        vol_per_bin = c_vol / max(1, bins_touched)
        
        for b in range(first_bin, last_bin + 1):
            profile_rows[b]['total'] += vol_per_bin
            profile_rows[b][c_type] += vol_per_bin

    # 4. Value Area Calculation
    total_volume = sum(r['total'] for r in profile_rows)
    va_volume_target = total_volume * (value_area_pct / 100.0)
    
    # POC
    poc_row = max(profile_rows, key=lambda x: x['total'])
    poc_price = poc_row['price']
    
    # Sort by volume descending for VA
    sorted_rows = sorted(profile_rows, key=lambda x: x['total'], reverse=True)
    
    va_rows = []
    acc_vol = 0
    for r in sorted_rows:
        if acc_vol < va_volume_target:
            va_rows.append(r['price'])
            acc_vol += r['total']
        else:
            break
            
    vah = max(va_rows) if va_rows else poc_price
    val = min(va_rows) if va_rows else poc_price

    return {
        'profile': profile_rows,
        'poc': float(poc_price),
        'vah': float(vah),
        'val': float(val),
        'total_volume': float(total_volume)
    }

def get_best_resolution(start_time, end_time, chart_tf):
    """
    Selects resolution to keep bars <= 5000.
    Priority: 1m -> 5m -> 15m -> 30m -> 60m -> 4h -> 1D
    """
    diff_seconds = end_time - start_time
    
    # Force 1s for very short ranges
    if diff_seconds <= 300 or 's' in chart_tf:
        return "1s"
        
    resolutions = [
        ("1min", 60),
        ("5min", 300),
        ("15min", 900),
        ("30min", 1800),
        ("1h", 3600),
        ("4h", 14400),
        ("1D", 86400)
    ]
    
    for tf_str, seconds in resolutions:
        count = diff_seconds / seconds
        if count <= 5000:
            return tf_str
            
    return "1D"

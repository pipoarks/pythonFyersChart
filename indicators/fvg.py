import pandas as pd
import numpy as np


def calculate_fvg(
    data,
    threshold_per=0,
    auto=False,                 # <-- Lux default behavior visually
    delete_mitigated=False,     # <-- set True to mimic box deletion
    mitigation_check=True,      # Added for compatibility
    only_today=False            # Added for filtering
):
    """
    TRUE LuxAlgo Fair Value Gap logic.
    """

    df = data.copy()
    
    # Optional: Filter for today's data only if requested
    if only_today and not df.empty:
        import datetime
        last_ts = df.index[-1]
        
        # Handle both unix timestamps and pandas Timestamps
        if isinstance(last_ts, (int, float, np.integer, np.floating)):
            # last_ts is already IST-shifted (unix + 19800)
            # We use utcfromtimestamp to get the date/time components as they would appear in IST
            dt = datetime.datetime.utcfromtimestamp(float(last_ts))
            # Start of day in IST-shifted terms
            start_of_day_ts = datetime.datetime(dt.year, dt.month, dt.day, tzinfo=datetime.timezone.utc).timestamp()
            df = df[df.index >= start_of_day_ts]
        else:
            # Assume pandas Timestamp
            start_of_day = last_ts.normalize() 
            df = df[df.index >= start_of_day]

    if df.empty or len(df) < 3:
        return []

    high = df['high'].to_numpy()
    low = df['low'].to_numpy()
    close = df['close'].to_numpy()

    n = len(df)

    # -----------------------------
    # Auto threshold (Lux method)
    # -----------------------------
    if auto:
        volatility = (high - low) / low
        cum_vol = np.cumsum(volatility)

        # Pine bar_index starts at 0,
        # but division by zero is avoided implicitly.
        bar_index = np.arange(n)
        bar_index[0] = 1

        threshold = cum_vol / bar_index
    else:
        threshold = np.full(n, threshold_per / 100)


    fvg_records = []
    last_fvg_time = None  # Lux uses ONE timestamp


    # =============================
    # DETECTION
    # =============================
    for i in range(2, n):

        t = df.index[i]
        th = threshold[i]

        # -------- Bullish --------
        bull = (
            low[i] > high[i-2]
            and close[i-1] > high[i-2]
            and (low[i] - high[i-2]) / high[i-2] > th
        )

        if bull and t != last_fvg_time:

            fvg_records.append({
                "index": i,
                "t": t,
                "max": low[i],      # top
                "min": high[i-2],   # bottom
                "isbull": True,
                "mitigated": False,
                "mitigation_time": None,
                "mitigation_index": None
            })

            last_fvg_time = t
            continue


        # -------- Bearish --------
        bear = (
            high[i] < low[i-2]
            and close[i-1] < low[i-2]
            and (low[i-2] - high[i]) / high[i] > th
        )

        if bear and t != last_fvg_time:

            fvg_records.append({
                "index": i,
                "t": t,
                "max": low[i-2],   # top
                "min": high[i],    # bottom
                "isbull": False,
                "mitigated": False,
                "mitigation_time": None,
                "mitigation_index": None
            })

            last_fvg_time = t


    # =============================
    # MITIGATION (exact Lux logic)
    # =============================
    for fvg in fvg_records:

        start = fvg["index"]

        if fvg["isbull"]:
            # mitigated when CLOSE < bottom
            mask = close[start+1:] < fvg["min"]
        else:
            # mitigated when CLOSE > top
            mask = close[start+1:] > fvg["max"]

        hit = np.argmax(mask) if mask.any() else None

        if hit is not None and mask.any():
            fvg["mitigated"] = True
            fvg["mitigation_index"] = start + 1 + hit
            fvg["mitigation_time"] = df.index[start + 1 + hit]


    # =============================
    # Optional deletion (matches box.delete)
    # =============================
    if delete_mitigated:
        fvg_records = [f for f in fvg_records if not f["mitigated"]]


    return fvg_records

import sqlite3
import pandas as pd

conn = sqlite3.connect("ticks.db")

df = pd.read_sql("""
    SELECT symbol, ltp, last_traded_time
    FROM ticks
    ORDER BY id DESC
    LIMIT 10
""", conn)

print(df)

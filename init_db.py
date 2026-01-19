import sqlite3

conn = sqlite3.connect("ticks.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE ticks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,
    ltp REAL,
    last_traded_time INTEGER,
    exch_feed_time INTEGER,
    last_traded_qty INTEGER,
    bid_price REAL,
    ask_price REAL,
    bid_size INTEGER,
    ask_size INTEGER,
    vol_traded_today INTEGER,
    tot_buy_qty INTEGER,
    tot_sell_qty INTEGER,
    avg_trade_price REAL,
    open_price REAL,
    high_price REAL,
    low_price REAL,
    prev_close_price REAL,
    ch REAL,
    chp REAL,
    recv_time INTEGER
)
""")

conn.commit()
conn.close()

print("✅ ticks.db created successfully")

import sqlite3

def init_db():
    conn = sqlite3.connect("candles_1min.db", timeout=5)
    cur = conn.cursor()

    # 🔑 CRITICAL PRAGMAS (RUN ONCE IS ENOUGH)
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA busy_timeout=5000;")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS candles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        timestamp INTEGER,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        tick_count INTEGER,
        UNIQUE(symbol, timestamp)
    )
    """)

    conn.commit()
    conn.close()
    print("✅ candles_1min.db initialized with WAL mode")

if __name__ == "__main__":
    init_db()

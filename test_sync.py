import requests
import json
import os

url = "http://127.0.0.1:5000/sync_watchlist"
try:
    print("Triggering sync...")
    resp = requests.post(url)
    if resp.ok:
        data = resp.json()
        print(f"Sync Success: {data['success']}")
        print(f"Count: {data['count']}")
        
        # Check config.json
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                config = json.load(f)
                print("\nWatchlist in config.json:")
                for item in config.get("watchlist", []):
                    print(f" - {item}")
    else:
        print(f"Sync Failed: {resp.status_code}")
except Exception as e:
    print(f"Error: {e}")

import pandas as pd
import requests
import io
import json

url = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

print("Downloading Nifty 500 list...")
response = requests.get(url, headers=headers)
response.raise_for_status()

df = pd.read_csv(io.StringIO(response.text))
symbols = df['Symbol'].tolist()

watchlist = []
for sym in symbols:
    watchlist.append({
        "ticker": sym,
        "name": sym, # Simplification
        "volume_multiplier": 2.0,
        "sentiment_pct": 5.0
    })

with open("watchlist.json", "w") as f:
    json.dump(watchlist, f, indent=2)

print(f"Generated watchlist.json with {len(watchlist)} stocks.")

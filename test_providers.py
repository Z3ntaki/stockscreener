import sys
from pprint import pprint
import yfinance as yf

print("--- jugaad_data test ---")
try:
    from jugaad_data.nse import NSELive
    n = NSELive()
    q = n.stock_quote("TCS")
    pprint(q)
except Exception as e:
    print(f"jugaad_data failed: {e}")

print("\n--- nsepython test ---")
try:
    from nsepython import nse_quote
    q = nse_quote("TCS")
    pprint(q)
except Exception as e:
    print(f"nsepython failed: {e}")

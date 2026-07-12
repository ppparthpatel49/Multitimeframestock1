import yfinance as yf
import pandas as pd
import requests
import io
from tqdm import tqdm

def fetch_official_nifty500():
    url = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        df = pd.read_csv(io.StringIO(response.text))
        return df['Symbol'].tolist() if 'Symbol' in df.columns else []
    except: return []

def validate_symbol(symbol):
    try:
        t = yf.Ticker(f"{symbol}.NS")
        if not t.history(period="1d").empty: return symbol
    except: pass
    return None

def main():
    raw = fetch_official_nifty500()
    if not raw: return
    verified = [v for s in raw if (v := validate_symbol(s))]
    pd.DataFrame({'symbol': verified}).to_csv("nifty500.csv", index=False)
    print(f"Verified {len(verified)} stocks.")

if __name__ == "__main__":
    main()

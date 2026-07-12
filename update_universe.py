import yfinance as yf
import pandas as pd
import requests
import io
from tqdm import tqdm
import os

def fetch_official_nifty500():
    """Fetch Nifty 500 list directly from official NSE archives using browser headers."""
    url = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
    
    # Mimic a real browser to avoid 403 Forbidden error from NSE
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.nseindia.com/'
    }

    try:
        print(f"Connecting to official NSE archives...")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() # Raise error for bad status codes
        
        # Load CSV from the response text
        df = pd.read_csv(io.StringIO(response.text))
        
        # NSE Official CSV uses 'Symbol' (case sensitive)
        if 'Symbol' in df.columns:
            return df['Symbol'].tolist()
        else:
            print("❌ Error: 'Symbol' column not found in official CSV.")
            return []
            
    except Exception as e:
        print(f"❌ Official NSE link failed: {e}")
        print("Falling back to community mirror...")
        # Fallback to the mirrored source if official is down/blocking
        try:
            mirror_url = "https://raw.githubusercontent.com/kprohith/nse-stock-analysis/refs/heads/master/ind_nifty500list.csv"
            df = pd.read_csv(mirror_url)
            col = 'Symbol' if 'Symbol' in df.columns else 'symbol'
            return df[col].tolist()
        except Exception as e2:
            print(f"❌ All sources failed: {e2}")
            return []

def validate_symbol(symbol):
    """Verify if the symbol is actually tradable/exists on yfinance."""
    try:
        clean_symbol = str(symbol).strip().upper().replace(" ", "")
        ticker_symbol = f"{clean_symbol}.NS" if not clean_symbol.endswith(".NS") else clean_symbol
        
        t = yf.Ticker(ticker_symbol)
        hist = t.history(period="1d")
        if not hist.empty:
            return clean_symbol
    except Exception:
        pass
    return None

def main():
    raw_symbols = fetch_official_nifty500()
    if not raw_symbols:
        print("Failed to fetch symbols. Exiting.")
        return

    print(f"Official list received: {len(raw_symbols)} symbols.")
    print("Validating symbols against Yahoo Finance to ensure data availability...")
    
    verified_symbols = []
    for s in tqdm(raw_symbols):
        valid = validate_symbol(s)
        if valid:
            verified_symbols.append(valid)

    print(f"\n✅ Validation Complete!")
    print(f"Official List: {len(raw_symbols)}")
    print(f"Verified Tradable: {len(verified_symbols)}")
    print(f"Filtered out: {len(raw_symbols) - len(verified_symbols)} (Invalid/Delisted)")

    # Save to CSV for the scanner
    df_final = pd.DataFrame({'symbol': verified_symbols})
    df_final.to_csv("python/nifty500.csv", index=False)
    print("Saved verified official list to python/nifty500.csv")

if __name__ == "__main__":
    main()

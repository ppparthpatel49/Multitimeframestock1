import pandas as pd
import os

# Hardcoded Nifty 200
NIFTY200_SYMBOLS = [
    "ADANIENT", "ADANIPORTS", "CUMMINSIND", "TATASTEEL", "TCS", "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA",
    "TITAN", "BAJFINANCE", "HCLTECH", "ULTRACEMCO", "WIPRO", "NTPC", "M&M", "JSWSTEEL", "POWERGRID",
    "ONGC", "COALINDIA", "BAJAJFINSV", "NESTLEIND", "GRASIM", "HINDALCO", "TECHM", "SBILIFE", "BPCL", "DRREDDY",
    "CIPLA", "EICHERMOT", "TATAMOTORS", "HDFCLIFE", "INDUSINDBK", "APOLLOHOSP", "BAJAJ-AUTO", "BRITANNIA", "DIVISLAB", "HINDZINC",
    "TATACONSUMER", "TATAELXSI", "LTIM", "PERSISTENT", "MPHASIS", "COFORGE", "POLICYBZR", "ZOMATO", "PAYTM", "NYKAA",
    "TRENT", "DELHIVERY", "YESBANK", "IDFCFIRSTB", "FEDERALBNK", "PNB", "CANBK", "BANKBARODA", "UNIONBANK", "INDIANB",
    "SBI", "BHEL", "BEL", "HAL", "MazagonDock", "COCHINSHIP", "IRFC", "RVNL", "IRCON", "SJVN",
    "TATACOMM", "TATAINVEST", "TATACHEM", "TATAPOWER"
]

def load_universe(mode="nifty500"):
    """Loads stock symbols from root directory files."""
    mode = mode.lower()
    
    if mode == "nifty200":
        return list(set([s.strip().upper() for s in NIFTY200_SYMBOLS]))

    elif mode == "nifty500":
        path = "nifty500.csv" # Look in root
        if os.path.exists(path):
            df = pd.read_csv(path)
            return df['symbol'].astype(str).tolist() if 'symbol' in df.columns else df.iloc[:, 0].astype(str).tolist()
        else:
            print(f"⚠️ Warning: {path} not found. Falling back to Nifty 200.")
            return load_universe("nifty200")

    elif mode == "custom":
        path = "universe.csv" # Look in root
        if os.path.exists(path):
            df = pd.read_csv(path)
            return df['symbol'].astype(str).tolist() if 'symbol' in df.columns else df.iloc[:, 0].astype(str).tolist()
        else:
            print(f"❌ Error: custom universe file {path} not found.")
            return []
    
    return load_universe("nifty200")

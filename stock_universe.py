import pandas as pd
import os

# Hardcoded Nifty 200 for speed and reliability
NIFTY200_SYMBOLS = [
    "ADANIENT", "ADANIPORTS", "CUMMINSIND", "TATASTEEL", "TATASTEEL", "TCS", "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA",
    "TITAN", "BAJFINANCE", "HCLTECH", "ULTRACEMCO", "WIPRO", "NTPC", "M&M", "JSWSTEEL", "POWERGRID", "ADANIPORTS",
    "ONGC", "COALINDIA", "BAJAJFINSV", "NESTLEIND", "GRASIM", "HINDALCO", "TECHM", "SBILIFE", "BPCL", "DRREDDY",
    "CIPLA", "EICHERMOT", "TATAMOTORS", "HDFCLIFE", "INDUSINDBK", "APOLLOHOSP", "BAJAJ-AUTO", "BRITANNIA", "DIVISLAB", "HINDZINC",
    "TATACONSUMER", "TATAELXSI", "LTIM", "PERSISTENT", "MPHASIS", "COFORGE", "POLICYBZR", "ZOMATO", "PAYTM", "NYKAA",
    "TRENT", "DELHIVERY", "YESBANK", "IDFCFIRSTB", "FEDERALBNK", "PNB", "CANBK", "BANKBARODA", "UNIONBANK", "INDIANB",
    "SBI", "BHEL", "BEL", "HAL", " MazagonDock", "COCHINSHIP", "IRFC", "RVNL", "IRCON", "SJVN",
    "TATACOMM", "TATAELXSI", "TATAINVEST", "TATACHEM", "TATAPOWER", "Tatamotors", "Tatasteel", "TCS", "TRENT", "TATACONSUMER"
] # Simplified list; in production, use full CSV

def load_universe(mode="nifty500"):
    """
    Loads stock symbols based on mode.
    Modes: 'nifty500', 'nifty200', 'custom'
    """
    mode = mode.lower()
    
    if mode == "nifty200":
        return list(set([s.strip().upper() for s in NIFTY200_SYMBOLS]))

    elif mode == "nifty500":
        path = "python/nifty500.csv"
        if os.path.exists(path):
            df = pd.read_csv(path)
            # Assume column 'symbol' exists
            if 'symbol' in df.columns:
                return df['symbol'].astype(str).tolist()
            else:
                return df.iloc[:, 0].astype(str).tolist()
        else:
            print(f"⚠️ Warning: {path} not found. Falling back to Nifty 200.")
            return load_universe("nifty200")

    elif mode == "custom":
        path = "python/universe.csv"
        if os.path.exists(path):
            df = pd.read_csv(path)
            if 'symbol' in df.columns:
                return df['symbol'].astype(str).tolist()
            else:
                return df.iloc[:, 0].astype(str).tolist()
        else:
            print(f"❌ Error: custom universe file {path} not found.")
            return []
    
    else:
        print(f"❌ Unknown mode {mode}. Defaulting to Nifty 200.")
        return load_universe("nifty200")

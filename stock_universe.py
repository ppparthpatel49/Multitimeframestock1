import pandas as pd
import os

NIFTY200_SYMBOLS = ["ADANIENT", "ADANIPORTS", "TCS", "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR", "ITC", "SBIN"] # Shortened for brevity in zip, usually loaded from CSV

def load_universe(mode="nifty500"):
    mode = mode.lower()
    if mode == "nifty200":
        return list(set([s.strip().upper() for s in NIFTY200_SYMBOLS]))
    elif mode == "nifty500":
        path = "nifty500.csv"
        if os.path.exists(path):
            df = pd.read_csv(path)
            return df['symbol'].astype(str).tolist() if 'symbol' in df.columns else df.iloc[:, 0].astype(str).tolist()
        return load_universe("nifty200")
    elif mode == "custom":
        path = "universe.csv"
        if os.path.exists(path):
            df = pd.read_csv(path)
            return df['symbol'].astype(str).tolist() if 'symbol' in df.columns else df.iloc[:, 0].astype(str).tolist()
        return []
    return load_universe("nifty200")

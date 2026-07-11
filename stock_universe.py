import pandas as pd
import yfinance as yf
import config
import os
import time

NIFTY200_SYMBOLS = [
"RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY","HINDUNILVR","SBIN","BHARTIARTL","ITC","LT",
"KOTAKBANK","AXISBANK","ASIANPAINT","MARUTI","BAJFINANCE","HCLTECH","TITAN","SUNPHARMA","TATAMOTORS","NTPC",
"ULTRACEMCO","POWERGRID","ONGC","TATASTEEL","WIPRO","ADANIENT","ADANIPORTS","JSWSTEEL","COALINDIA","TECHM",
"GRASIM","HINDALCO","CIPLA","TATACONSUM","BRITANNIA","EICHERMOT","DIVISLAB","BPCL","SBILIFE","DRREDDY",
"APOLLOHOSP","BAJAJFINSV","HEROMOTOCO","BAJAJ-AUTO","INDUSINDBK","HDFCLIFE","UPL","SHREECEM","ADANIGREEN","PIDILITIND",
"INDIGO","TATAPOWER","VEDL","SIEMENS","IOC","TRENT","DLF","VBL","AMBUJACEM","BANKBARODA","BEL","HAVELLS",
"CHOLAFIN","M&M","GAIL","ZOMATO","DABUR","DMART","ICICIPRULI","ICICIGI","GODREJCP","TORNTPHARM","MARICO","BERGEPAINT",
"SRF","JINDALSTEL","ABB","HDFCAMC","MPHASIS","PERSISTENT","COLPAL","MUTHOOTFIN","AUROPHARMA","LUPIN","BOSCHLTD","LTIM",
"MRF","CUMMINSIND","PIIND","TATACOMM","CANBK","BANDHANBNK","SAIL","NMDC","HINDPETRO","CONCOR","BHEL","HINDCOPPER",
"IRCTC","HAL","POLYCAB","TATACHEM","ASHOKLEY","AARTIIND","ALKEM","BALKRISIND","ESCORTS","GODREJPROP","OBEROIRLTY","MOTHERSON",
"PAGEIND","PFIZER","TORNTPOWER","CROMPTON","APOLLOTYRE","BHARATFORG","FEDERALBNK","IDFCFIRSTB","GMRINFRA","BANKINDIA","UNIONBANK","L&TFH",
"TVSMOTOR","ABCAPITAL","MANAPPURAM","AUBANK","MCDOWELL-N","UBL","JUBLFOOD","BATAINDIA","VOLTAS","PETRONET","IGL","MGL",
"ACC","ADANITRANS","ATGL","NAUKRI","PEL","BIOCON","COFORGE","DEEPAKNTR","TATAELXSI","LTTS","OFSS",
"GLAND","LAURUSLABS","IPCALAB","AJANTPHARM","LALPATHLAB","FORTIS","METROPOLIS","ABBOTINDIA",
"ASTRAL","KANSAINER","AKZOINDIA","ATUL","COROMANDEL","RALLIS",
"BALRAMCHIN","SUPREMEIND","HINDZINC","RAMCOCEM","JKCEMENT","DALBHARAT"
]

# deduplicate preserving order
def _dedup(seq):
    seen=set(); out=[]
    for x in seq:
        if x not in seen:
            seen.add(x); out.append(x)
    return out

NIFTY200_SYMBOLS = _dedup(NIFTY200_SYMBOLS)

def load_universe(mode=None, path=None):
    """
    mode: NIFTY500 | NIFTY200 | CUSTOM
    returns (tickers_with_.NS, symbols_plain)
    """
    mode = (mode or config.UNIVERSE_MODE).upper()
    if mode == "NIFTY500":
        f = config.NIFTY500_FILE
        if os.path.exists(f):
            df = pd.read_csv(f)
        else:
            try:
                url = "https://raw.githubusercontent.com/kprohith/nse-stock-analysis/master/ind_nifty500list.csv"
                df = pd.read_csv(url)
                df = df.rename(columns={"Symbol":"symbol","Company Name":"name","Industry":"sector"})
                try:
                    df.to_csv(f, index=False)
                except Exception:
                    pass
            except Exception:
                df = pd.DataFrame({"symbol": NIFTY200_SYMBOLS})
        symbols = df['symbol'].dropna().astype(str).str.strip().str.upper().unique().tolist()
        print(f"[Universe] NIFTY500 loaded: {len(symbols)} symbols")
    elif mode == "NIFTY200":
        symbols = NIFTY200_SYMBOLS
        print(f"[Universe] NIFTY200 embedded: {len(symbols)} symbols")
    else:
        p = path or config.UNIVERSE_FILE
        try:
            df = pd.read_csv(p, comment='#')
            symbols = df['symbol'].dropna().str.strip().str.upper().unique().tolist()
            print(f"[Universe] CUSTOM loaded: {len(symbols)} from {p}")
        except Exception as e:
            print(f"Universe load failed: {e}, using NIFTY200 fallback")
            symbols = NIFTY200_SYMBOLS

    # clean / unique
    seen=set(); uniq=[]
    for s in symbols:
        s = str(s).strip().upper()
        if s and s not in seen:
            seen.add(s); uniq.append(s)
    symbols = uniq

    # yfinance tickers – keep NSE special chars intact
    tickers = []
    for s in symbols:
        if s.startswith("^") or "." in s:
            tickers.append(s)
        else:
            tickers.append(s + ".NS")
    return tickers, symbols

def get_universe(*args, **kwargs):
    return load_universe(*args, **kwargs)

def _safe_float(x):
    try:
        import numpy as np
        if isinstance(x, (pd.Series, np.ndarray, list)):
            x = pd.Series(x).dropna().iloc[-1] if len(pd.Series(x).dropna()) else np.nan
        return float(x)
    except Exception:
        return float('nan')

def get_nifty_regime(ticker=None):
    """Returns BULL / NEUTRAL / BEAR based on Nifty weekly > 20EMA – robust to yfinance quirks"""
    sym = ticker or config.REGIME_SYMBOL
    try:
        # try Ticker history first – more stable in CI
        tk = yf.Ticker(sym)
        df = tk.history(period="2y", interval="1wk", auto_adjust=True)
        if df is None or df.empty or 'Close' not in df.columns:
            # fallback download
            df = yf.download(sym, period="1y", interval="1wk", progress=False, auto_adjust=True)
        if df is None or df.empty:
            return "UNKNOWN", {"error": "empty"}
        # flatten multiindex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        close_s = df['Close'].dropna()
        if len(close_s) < 25:
            return "NEUTRAL ⚠️", {"close": float(close_s.iloc[-1]) if len(close_s) else 0}
        ema20 = close_s.ewm(span=20, adjust=False).mean()
        c_last = _safe_float(close_s.iloc[-1])
        e_last = _safe_float(ema20.iloc[-1])
        e_prev = _safe_float(ema20.iloc[-2]) if len(ema20)>1 else e_last
        if pd.isna(c_last) or pd.isna(e_last):
            return "UNKNOWN", {}
        above = c_last > e_last
        slope_up = e_last > e_prev
        regime = "BULL ✅" if above and slope_up else "NEUTRAL ⚠️" if above else "BEAR ❌"
        return regime, {"close": round(c_last,2), "ema20": round(e_last,2)}
    except Exception as e:
        return f"ERROR: {str(e)[:120]}", {}

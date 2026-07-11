import pandas as pd
import yfinance as yf
import config
import os

NIFTY200_SYMBOLS = [
"RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY","HINDUNILVR","SBIN","BHARTIARTL","ITC","LT",
"KOTAKBANK","AXISBANK","ASIANPAINT","MARUTI","BAJFINANCE","HCLTECH","TITAN","SUNPHARMA","TATAMOTORS","NTPC",
"ULTRACEMCO","POWERGRID","ONGC","TATASTEEL","WIPRO","ADANIENT","ADANIPORTS","JSWSTEEL","COALINDIA","TECHM",
"GRASIM","HINDALCO","CIPLA","TATACONSUM","BRITANNIA","EICHERMOT","DIVISLAB","BPCL","SBILIFE","DRREDDY",
"APOLLOHOSP","BAJAJFINSV","HEROMOTOCO","BAJAJ-AUTO","INDUSINDBK","HDFCLIFE","UPL","SHREECEM","ADANIGREEN","PIDILITIND",
"INDIGO","TATAPOWER","VEDL","SIEMENS","IOC","TRENT","DLF","VBL","AMBUJACEM","BANKBARODA","BEL","HAVELLS",
"CHOLAFIN","M&M","GAIL","ZOMATO","DABUR","DMART","ICICIPRULI","ICICIGI","GODREJCP","TORNTPHARM","MARICO","BERGEPAINT",
"SRF","JINDALSTEL","ABB","HDFCAMC","MPHASIS","PERSISTENT","COLPAL","MUTHOOTFIN","AUROPHARMA","LUPIN","BOSCHLTD","LTI",
"MRF","CUMMINSIND","PIIND","TATACOMM","CANBK","BANDHANBNK","SAIL","NMDC","HINDPETRO","CONCOR","BHEL","HINDCOPPER",
"IRCTC","HAL","POLYCAB","TATACHEM","ASHOKLEY","AARTIIND","ALKEM","BALKRISIND","ESCORTS","GODREJPROP","OBEROIRLTY","MOTHERSON",
"PAGEIND","PFIZER","TORNTPOWER","CROMPTON","APOLLOTYRE","BHARATFORG","FEDERALBNK","IDFCFIRSTB","GMRINFRA","BANKINDIA","UNIONBANK","L&TFH",
"TVSMOTOR","ABCAPITAL","MANAPPURAM","AUBANK","MCDOWELL-N","UBL","JUBLFOOD","BATAINDIA","VOLTAS","PETRONET","IGL","MGL",
"ACC","ADANITRANS","ATGL","ADANIGAS","NAUKRI","PEL","BIOCON","BANDHAN","DEEPAKNTR","TATAELXSI","COFORGE","LTTS","MINDTREE","OFSS",
"GLAND","LAURUSLABS","IPCALAB","AJANTPHARM","APLLTD","TORNTPHARM","LALPATHLAB","FORTIS","APOLLOHOSP","METROPOLIS","ABBOTINDIA","ALEMBICLTD",
"ASTRAL","ASIANPAINT","KANSAINER","BERGEPAINT","AKZOINDIA","PIDILITIND","ATUL","DEEPAKFERT","GNFC","COROMANDEL","UPL","PIIND","RALLIS",
"SRF","AARTIIND","BALRAMCHIN","TATACHEM","SUPREMEIND","JINDALSTEL","JSWSTEEL","TATASTEEL","SAIL","HINDALCO","VEDL","COALINDIA","NMDC","HINDZINC",
"ULTRACEMCO","SHREECEM","AMBUJACEM","ACC","RAMCOCEM","JKCEMENT","DALBHARAT","GRASIM"
]

def load_universe(mode=None, path=None):
    """
    mode: NIFTY500 | NIFTY200 | CUSTOM
    returns (tickers_with_.NS, symbols_plain)
    """
    mode = (mode or config.UNIVERSE_MODE).upper()
    if mode == "NIFTY500":
        # try local nifty500.csv first
        f = config.NIFTY500_FILE
        if os.path.exists(f):
            df = pd.read_csv(f)
        else:
            # fallback to embedded list via download attempt
            try:
                url = "https://raw.githubusercontent.com/kprohith/nse-stock-analysis/master/ind_nifty500list.csv"
                df = pd.read_csv(url)
                df = df.rename(columns={"Symbol":"symbol","Company Name":"name","Industry":"sector"})
                df.to_csv(f, index=False)
            except Exception:
                df = pd.DataFrame({"symbol": NIFTY200_SYMBOLS})
        symbols = df['symbol'].dropna().astype(str).str.strip().str.upper().unique().tolist()
        print(f"[Universe] NIFTY500 loaded: {len(symbols)} symbols from {f if os.path.exists(f) else 'fallback'}")
    elif mode == "NIFTY200":
        symbols = NIFTY200_SYMBOLS
        print(f"[Universe] NIFTY200 embedded: {len(symbols)} symbols")
    else:  # CUSTOM
        p = path or config.UNIVERSE_FILE
        try:
            df = pd.read_csv(p, comment='#')
            symbols = df['symbol'].dropna().str.strip().str.upper().unique().tolist()
            print(f"[Universe] CUSTOM loaded: {len(symbols)} from {p}")
        except Exception as e:
            print(f"Universe load failed: {e}, using NIFTY200 fallback")
            symbols = NIFTY200_SYMBOLS

    # unique preserve order, keep NSE symbols intact for yfinance
    seen=set()
    uniq=[]
    for s in symbols:
        s = str(s).strip().upper()
        if s and s not in seen:
            seen.add(s)
            uniq.append(s)
    symbols = uniq
    # yfinance tickers
    tickers = []
    for s in symbols:
        if "." in s or "^" in s or s.endswith(".NS") or s.endswith(".BO"):
            tickers.append(s)
        else:
            tickers.append(s + ".NS")
    return tickers, symbols

# backward compat
def get_universe(*args, **kwargs):
    return load_universe(*args, **kwargs)

def get_nifty_regime():
    """Returns BULL / NEUTRAL / BEAR based on Nifty weekly > 20EMA"""
    try:
        df = yf.download(config.REGIME_SYMBOL, period="1y", interval="1wk", progress=False, auto_adjust=True)
        if df.empty:
            return "UNKNOWN", {}
        df['ema20'] = df['Close'].ewm(span=20, adjust=False).mean()
        last = df.iloc[-1]
        last2 = df.iloc[-2] if len(df) > 1 else last
        close = float(last['Close'])
        ema = float(last['ema20'])
        above = close > ema
        slope_up = ema > float(last2['ema20'])
        regime = "BULL ✅" if above and slope_up else "NEUTRAL ⚠️" if above else "BEAR ❌"
        return regime, {"close": round(close,2), "ema20": round(ema,2)}
    except Exception as e:
        return f"ERROR: {e}", {}

import yfinance as yf
import pandas as pd
import numpy as np
from pandas_ta import rsi
from tqdm import tqdm
import config

def flatten_columns(df):
    """Handles yfinance MultiIndex column quirk."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def fetch_index_data(symbol, start, end):
    """Fetch benchmark index data for RS calculation."""
    print(f"Fetching benchmark index: {symbol}...")
    df = yf.download(symbol, start=start, end=end, progress=False)
    df = flatten_columns(df)
    if df.empty:
        raise ValueError(f"Could not fetch data for index {symbol}")
    return df['Close']

def analyze_ticker(symbol, index_close, start, end):
    """Analyze stock using Premium MTF-RSI + RS + Volume logic strictly aligned with yfinance."""
    try:
        # 1. Fetch and Flatten
        # Add .NS only if it's not the index and doesn't have it
        ticker_symbol = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
        df = yf.download(ticker_symbol, start=start, end=end, progress=False)
        df = flatten_columns(df)
        
        if len(df) < 60: return None

        close = df['Close']
        volume = df['Volume']

        # --- 2. MTF-RSI Logic (Correct Resampling) ---
        # Daily RSI
        rsi_d_series = rsi(close, length=config.RSI_LEN)
        
        # Weekly RSI: Resample Close -> Calculate RSI -> Map back to Daily
        df_w_close = close.resample('W').last()
        rsi_w_values = rsi(df_w_close, length=config.RSI_LEN)
        # Convert to series with index and ffill to match daily dates
        rsi_w_daily = pd.Series(rsi_w_values.values, index=df_w_close.index).reindex(close.index, method='ffill')
        
        # Monthly RSI: Resample Close -> Calculate RSI -> Map back to Daily
        df_m_close = close.resample('ME').last()
        rsi_m_values = rsi(df_m_close, length=config.RSI_LEN)
        # Convert to series with index and ffill to match daily dates
        rsi_m_daily = pd.Series(rsi_m_values.values, index=df_m_close.index).reindex(close.index, method='ffill')

        curr_rsi_d = rsi_d_series.iloc[-1]
        curr_rsi_w = rsi_w_daily.iloc[-1]
        curr_rsi_m = rsi_m_daily.iloc[-1]
        
        rsi_aligned = (curr_rsi_d > config.RSI_THRESHOLD and 
                       curr_rsi_w > config.RSI_THRESHOLD and 
                       curr_rsi_m > config.RSI_THRESHOLD)

        # --- 3. Relative Strength (RS) Logic ---
        # Align Nifty index close to the stock's close dates
        idx_aligned = index_close.reindex(close.index, method='ffill')
        
        # Performance Comparison (Stock return vs Index return over last 63 days)
        lookback = 63
        if len(close) >= lookback:
            stock_return = (close.iloc[-1] - close.iloc[-lookback]) / close.iloc[-lookback]
            index_return = (idx_aligned.iloc[-1] - idx_aligned.iloc[-lookback]) / idx_aligned.iloc[-lookback]
            rs_bullish = stock_return > index_return
        else:
            rs_bullish = False

        # --- 4. Volume Footprint Logic ---
        avg_vol = volume.rolling(config.VOL_SMA_LEN).mean()
        vol_ratio = volume.iloc[-1] / avg_vol.iloc[-1]
        vol_bullish = (vol_ratio > config.VOL_MULT) and (close.iloc[-1] > df['Open'].iloc[-1])

        # --- Scoring ---
        score = 0
        reasons = []
        if rsi_aligned: 
            score += 1
            reasons.append("RSI")
        if rs_bullish: 
            score += 1
            reasons.append("RS")
        if vol_bullish: 
            score += 1
            reasons.append("Vol")

        return {
            'symbol': symbol,
            'score': score,
            'reasons': reasons,
            'price': float(close.iloc[-1]),
            'rsi_d': float(curr_rsi_d),
            'vol_ratio': float(vol_ratio)
        }
    except Exception as e:
        # print(f"Error analyzing {symbol}: {e}")
        return None

def scan_universe(symbols, start, end):
    # Fetch index data once for the whole scan to avoid yfinance rate limits
    try:
        index_close = fetch_index_data(config.INDEX_SYMBOL, start, end)
    except Exception as e:
        print(f"❌ Critical Error fetching index: {e}")
        return {'signals': [], 'watchlist': [], 'eligible': []}
    
    signals = []
    watchlist = []
    eligible = []

    for s in tqdm(symbols):
        res = analyze_ticker(s, index_close, start, end)
        if res:
            if res['score'] == 3:
                signals.append(res)
            elif res['score'] == 2:
                watchlist.append(res)
            elif res['score'] == 1:
                eligible.append(res)
                
    return {
        'signals': signals,
        'watchlist': watchlist,
        'eligible': eligible
    }

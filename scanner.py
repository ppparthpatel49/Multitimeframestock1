import yfinance as yf
import pandas as pd
import numpy as np
from pandas_ta import rsi
from tqdm import tqdm
import config

def flatten_columns(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def fetch_index_data(symbol, start, end):
    df = yf.download(symbol, start=start, end=end, progress=False)
    df = flatten_columns(df)
    return df['Close']

def analyze_ticker(symbol, index_close, start, end):
    try:
        ticker_symbol = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
        df = yf.download(ticker_symbol, start=start, end=end, progress=False)
        df = flatten_columns(df)
        if len(df) < 60: return None
        close = df['Close']
        volume = df['Volume']
        
        # 1. MTF RSI
        rsi_d = rsi(close, length=config.RSI_LEN)
        df_w = close.resample('W').last()
        rsi_w_vals = rsi(df_w, length=config.RSI_LEN)
        rsi_w_daily = pd.Series(rsi_w_vals.values, index=df_w.index).reindex(close.index, method='ffill')
        df_m = close.resample('ME').last()
        rsi_m_vals = rsi(df_m, length=config.RSI_LEN)
        rsi_m_daily = pd.Series(rsi_m_vals.values, index=df_m.index).reindex(close.index, method='ffill')
        
        curr_rsi_d = rsi_d.iloc[-1]
        curr_rsi_w = rsi_w_daily.iloc[-1]
        curr_rsi_m = rsi_m_daily.iloc[-1]
        rsi_aligned = (curr_rsi_d > config.RSI_THRESHOLD and curr_rsi_w > config.RSI_THRESHOLD and curr_rsi_m > config.RSI_THRESHOLD)
        
        # 2. Relative Strength
        idx_aligned = index_close.reindex(close.index, method='ffill')
        stock_ret = (close.iloc[-1] - close.iloc[-config.RS_LOOKBACK]) / close.iloc[-config.RS_LOOKBACK]
        idx_ret = (idx_aligned.iloc[-1] - idx_aligned.iloc[-config.RS_LOOKBACK]) / idx_aligned.iloc[-config.RS_LOOKBACK]
        rs_bullish = stock_ret > idx_ret
        
        # 3. Volume
        avg_vol = volume.rolling(config.VOL_SMA_LEN).mean()
        vol_ratio = volume.iloc[-1] / avg_vol.iloc[-1]
        vol_bullish = (vol_ratio > config.VOL_MULT) and (close.iloc[-1] > df['Open'].iloc[-1])
        
        score = 0
        reasons = []
        if rsi_aligned: score += 1; reasons.append("RSI")
        if rs_bullish: score += 1; reasons.append("RS")
        if vol_bullish: score += 1; reasons.append("Vol")
        
        return {
            'symbol': symbol, 
            'score': score, 
            'reasons': reasons, 
            'price': float(close.iloc[-1]), 
            'rsi_d': float(curr_rsi_d), 
            'vol_ratio': float(vol_ratio),
            'metrics': {'rsi': rsi_aligned, 'rs': rs_bullish, 'vol': vol_bullish}
        }
    except: return None

def scan_universe(symbols, start, end):
    index_close = fetch_index_data(config.INDEX_SYMBOL, start, end)
    signals, watchlist, eligible = [], [], []
    
    # Diagnostics counters
    stats = {'total': 0, 'rsi_pass': 0, 'rs_pass': 0, 'vol_pass': 0}

    for s in tqdm(symbols):
        res = analyze_ticker(s, index_close, start, end)
        if res:
            stats['total'] += 1
            if res['metrics']['rsi']: stats['rsi_pass'] += 1
            if res['metrics']['rs']: stats['rs_pass'] += 1
            if res['metrics']['vol']: stats['vol_pass'] += 1
            
            if res['score'] == 3: signals.append(res)
            elif res['score'] == 2: watchlist.append(res)
            elif res['score'] == 1: eligible.append(res)
                
    return {
        'signals': signals, 
        'watchlist': watchlist, 
        'eligible': eligible, 
        'stats': stats
    }

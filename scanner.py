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
        rsi_d = rsi(close, length=config.RSI_LEN)
        df_w = close.resample('W').last()
        rsi_w_vals = rsi(df_w['Close'], length=config.RSI_LEN)
        rsi_w_daily = pd.Series(rsi_w_vals.values, index=df_w.index).reindex(close.index, method='ffill')
        df_m = close.resample('ME').last()
        rsi_m_vals = rsi(df_m['Close'], length=config.RSI_LEN)
        rsi_m_daily = pd.Series(rsi_m_vals.values, index=df_m.index).reindex(close.index, method='ffill')
        curr_rsi_d = rsi_d.iloc[-1]
        curr_rsi_w = rsi_w_daily.iloc[-1]
        curr_rsi_m = rsi_m_daily.iloc[-1]
        rsi_aligned = (curr_rsi_d > config.RSI_THRESHOLD and curr_rsi_w > config.RSI_THRESHOLD and curr_rsi_m > config.RSI_THRESHOLD)
        idx_aligned = index_close.reindex(close.index, method='ffill')
        lookback = config.RS_LOOKBACK
        stock_ret = (close.iloc[-1] - close.iloc[-lookback]) / close.iloc[-lookback]
        idx_ret = (idx_aligned.iloc[-1] - idx_aligned.iloc[-lookback]) / idx_aligned.iloc[-lookback]
        rs_bullish = stock_ret > idx_ret
        avg_vol = volume.rolling(config.VOL_SMA_LEN).mean()
        vol_ratio = volume.iloc[-1] / avg_vol.iloc[-1]
        vol_bullish = (vol_ratio > config.VOL_MULT) and (close.iloc[-1] > df['Open'].iloc[-1])
        score = 0
        reasons = []
        if rsi_aligned: score += 1; reasons.append("RSI")
        if rs_bullish: score += 1; reasons.append("RS")
        if vol_bullish: score += 1; reasons.append("Vol")
        return {'symbol': symbol, 'score': score, 'reasons': reasons, 'price': float(close.iloc[-1]), 'rsi_d': float(curr_rsi_d), 'vol_ratio': float(vol_ratio)}
    except Exception: return None

def scan_universe(symbols, start, end):
    index_close = fetch_index_data(config.INDEX_SYMBOL, start, end)
    signals, watchlist, eligible = [], [], []
    for s in tqdm(symbols):
        res = analyze_ticker(s, index_close, start, end)
        if res:
            if res['score'] == 3: signals.append(res)
            elif res['score'] == 2: watchlist.append(res)
            elif res['score'] == 1: eligible.append(res)
    return {'signals': signals, 'watchlist': watchlist, 'eligible': eligible}

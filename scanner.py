#!/usr/bin/env python3
import yfinance as yf
import pandas as pd
import numpy as np
from tqdm import tqdm
import argparse, json, os
from datetime import datetime, timedelta
import pytz
import config
from stock_universe import load_universe, get_nifty_regime
from risk_calculator import position_size

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    down = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / down.replace(0, np.nan)
    return 100 - (100/(1+rs))

def atr(df, n=14):
    h,l,c = df['High'], df['Low'], df['Close']
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def analyze_ticker(ticker):
    try:
        dfd = yf.download(ticker, period="420d", interval="1d", progress=False, auto_adjust=True)
        if dfd.empty or len(dfd) < 150:
            return None
        # daily indicators
        dfd['atr'] = atr(dfd, config.ATR_LEN)
        dfd['atr_pct'] = dfd['atr'] / dfd['Close'] * 100
        dfd['vol_sma20'] = dfd['Volume'].rolling(20).mean()
        dfd['rsi'] = rsi(dfd['Close'],14)

        last = dfd.iloc[-1]
        prev = dfd.iloc[-2] if len(dfd)>1 else last
        close = float(last['Close'])
        atr_v = float(last['atr'])
        atr_pct = float(last['atr_pct'])
        vol = float(last['Volume'])
        vol_sma = float(last['vol_sma20'])
        rsi_d = float(last['rsi'])

        # weekly breakout
        dfw = dfd['Close'].resample('W-FRI').last()
        dfh = dfd['High'].resample('W-FRI').max()
        dfv = dfd['Volume'].resample('W-FRI').sum()
        if len(dfw) < config.WEEKLY_LOOKBACK + 2:
            return None
        weekly_high = float(dfh.iloc[-2-config.WEEKLY_LOOKBACK:-1].max())  # confirmed prior weeks
        weekly_close_prev = float(dfw.iloc[-2])
        breakout = close > weekly_high
        near_breakout = close >= weekly_high * 0.985

        # monthly trend
        dfm = dfd['Close'].resample('ME').last()
        if len(dfm) < 25:
            m_trend = False; m_ema_fast_v=0; m_ema_slow_v=0
        else:
            m_ef = ema(dfm, config.M_EMA_FAST)
            m_es = ema(dfm, config.M_EMA_SLOW)
            m_close = float(dfm.iloc[-1])
            m_ema_fast_v = float(m_ef.iloc[-1])
            m_ema_slow_v = float(m_es.iloc[-1])
            m_rsi = float(rsi(dfm,14).iloc[-1]) if len(dfm)>14 else 50
            m_trend = m_close > m_ema_fast_v and m_ema_fast_v > m_ema_slow_v and m_rsi > 50

        # quarterly / 3M momentum – approximate with 63d daily
        if len(dfd) > 70:
            q_close = close
            q_ema63 = float(dfd['Close'].ewm(span=63, adjust=False).mean().iloc[-1])
            roc63 = (close / float(dfd['Close'].iloc[-64]) - 1) * 100 if len(dfd) > 64 else 0
            q_rsi_val = float(rsi(dfd['Close'],14).rolling(63).mean().iloc[-1]) if not np.isnan(rsi_d) else rsi_d
            # better: 63d RSI
            rsi63_series = rsi(dfd['Close'],14)
            q_rsi_val = float(rsi63_series.iloc[-1])
            q_mom = q_close > q_ema63 and q_rsi_val > config.Q_RSI_MIN and roc63 > config.Q_ROC_MIN
        else:
            q_mom=False; roc63=0; q_rsi_val=rsi_d; q_ema63=close

        # volume crore approx
        vol_crore = vol * close / 1e7

        # filters
        vol_ok = vol > vol_sma * config.VOL_MULT if not np.isnan(vol_sma) else False
        volatility_ok = config.MIN_ATR_PCT <= atr_pct <= config.MAX_ATR_PCT
        rsi_ok = rsi_d > 50
        price_ok = close > config.__dict__.get('MIN_PRICE', 50)
        liquidity_ok = vol_crore >= config.MIN_VOLUME_CRORE

        signal = breakout and m_trend and q_mom and vol_ok and volatility_ok and rsi_ok
        watch = near_breakout and m_trend and q_mom

        sl_price = close - atr_v * config.SL_ATR_MULT
        risk_ps = close - sl_price

        ps = position_size(close, sl_price)

        return {
            "ticker": ticker,
            "symbol": ticker.replace(".NS",""),
            "close": round(close,2),
            "weekly_high": round(weekly_high,2),
            "breakout": bool(breakout),
            "near": bool(near_breakout),
            "m_trend": bool(m_trend),
            "q_mom": bool(q_mom),
            "q_roc63": round(roc63,1),
            "q_rsi": round(q_rsi_val,1),
            "atr_pct": round(atr_pct,2),
            "vol_x": round(vol/vol_sma,2) if vol_sma else 0,
            "vol_cr": round(vol_crore,1),
            "rsi_d": round(rsi_d,1),
            "sl": round(sl_price,2),
            "risk_ps": round(risk_ps,2),
            "tp1": ps["tp1"],
            "tp2": ps["tp2"],
            "qty": ps["qty_final"],
            "capital": ps["capital_used"],
            "signal": bool(signal),
            "watch": bool(watch),
            "filters": {
                "vol_ok": bool(vol_ok),
                "volatility_ok": bool(volatility_ok),
                "liquidity_ok": bool(liquidity_ok),
                "price_ok": bool(price_ok)
            },
            "score": int(q_mom) + int(m_trend) + int(breakout) + int(vol_ok) + int(volatility_ok)
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}

def scan_universe(save_json=True, mode=None, limit=None):
    tickers, symbols = load_universe(mode=mode)
    if limit:
        tickers = tickers[:limit]
        symbols = symbols[:limit]
    results=[]
    for t in tqdm(tickers, desc="TDMB Scan"):
        r = analyze_ticker(t)
        if r and not r.get("error"):
            results.append(r)
    # sort
    # Tiers:
    # 1. signals = full breakout + HTF + vol
    # 2. watch = near breakout + HTF
    # 3. eligible = q_mom + m_trend (top-down pass) – ALL ELIGIBLE CANDIDATES
    # 4. breakout_only = breakout true but HTF maybe weak
    signals = [x for x in results if x.get("signal")]
    watches = [x for x in results if x.get("watch") and not x.get("signal")]
    eligible_htf = [x for x in results if x.get("q_mom") and x.get("m_trend")]
    breakout_only = [x for x in results if x.get("breakout")]

    signals.sort(key=lambda x: (x["score"], x["vol_x"], x["q_roc63"]), reverse=True)
    watches.sort(key=lambda x: (x["score"], x["vol_x"]), reverse=True)
    eligible_htf.sort(key=lambda x: (x["q_roc63"], x["vol_x"]), reverse=True)
    breakout_only.sort(key=lambda x: x["vol_x"], reverse=True)

    regime, regime_info = get_nifty_regime()
    out = {
        "timestamp_ist": datetime.now(pytz.timezone(config.IST)).isoformat(),
        "regime": regime,
        "regime_info": regime_info,
        "signals": signals,
        "watchlist": watches,   # full list – Telegram will chunk
        "eligible": eligible_htf,
        "breakout_only": breakout_only,
        "scanned": len(results),
        "universe_mode": mode or config.UNIVERSE_MODE
    }
    if save_json:
        os.makedirs("output", exist_ok=True)
        with open("output/last_scan.json","w") as f:
            json.dump(out,f,indent=2)
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true", help="send via telegram (use main.py)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--universe", "-u", choices=["NIFTY500","NIFTY200","CUSTOM"], default=None, help="override UNIVERSE_MODE")
    ap.add_argument("--limit", type=int, default=None, help="scan first N symbols (debug)")
    args = ap.parse_args()
    res = scan_universe(mode=args.universe, limit=args.limit)
    print(f"Nifty Regime: {res['regime']}")
    print(f"Signals: {len(res['signals'])}  Watch: {len(res['watchlist'])}  Eligible HTF: {len(res['eligible'])} / Scanned {res['scanned']}")
    print("\n--- BREAKOUT SIGNALS ---")
    for s in res["signals"][:20]:
        print(f"{s['symbol']:14} ₹{s['close']} > W12 {s['weekly_high']} | SL {s['sl']} | Qty {s['qty']} | Vol {s['vol_x']}x | ATR {s['atr_pct']}% | 3M {s['q_roc63']}%")
    if res["watchlist"]:
        print("\n--- WATCH NEAR BREAKOUT ---")
        for w in res["watchlist"][:10]:
            print(f"{w['symbol']:14} ₹{w['close']}/{w['weekly_high']}  Vol {w['vol_x']}x  3M {w['q_roc63']}%")
    if args.json:
        print(json.dumps(res, indent=2))

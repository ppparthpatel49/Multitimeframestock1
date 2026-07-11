#!/usr/bin/env python3
import yfinance as yf
import pandas as pd
import numpy as np
from tqdm import tqdm
import argparse, json, os, time, random
from datetime import datetime
import pytz
import config
from stock_universe import load_universe, get_nifty_regime
from risk_calculator import position_size

def ema(s, n): 
    return s.ewm(span=n, adjust=False).mean() if s is not None and len(s) else s

def rsi(s, n=14):
    if s is None or len(s) < n+1:
        return pd.Series(index=s.index if hasattr(s,'index') else [], dtype=float)
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    down = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / down.replace(0, np.nan)
    return 100 - (100/(1+rs))

def atr(df, n=14):
    h,l,c = df['High'], df['Low'], df['Close']
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def _flatten_cols(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def _safe_float(v, default=np.nan):
    try:
        if isinstance(v, pd.Series):
            v = v.dropna().iloc[-1] if not v.dropna().empty else default
        return float(v)
    except Exception:
        return float(default)

def fetch_daily(ticker, tries=3):
    """Robust yfinance fetch – handles CI rate limits"""
    last_err = None
    for attempt in range(tries):
        try:
            # Try Ticker.history first – more stable in GH Actions
            tk = yf.Ticker(ticker)
            df = tk.history(period="2y", interval="1d", auto_adjust=True, timeout=20)
            if df is None or df.empty or len(df) < 100:
                # fallback download
                df = yf.download(ticker, period="420d", interval="1d", progress=False, auto_adjust=True, threads=False, timeout=20)
            if df is not None and not df.empty:
                df = _flatten_cols(df)
                # ensure required cols
                for c in ['Open','High','Low','Close','Volume']:
                    if c not in df.columns:
                        raise ValueError(f"missing {c}")
                return df
            last_err = "empty"
        except Exception as e:
            last_err = str(e)
        # exponential backoff + jitter
        time.sleep(0.8 + attempt*1.2 + random.uniform(0,0.6))
    raise RuntimeError(f"fetch failed {ticker}: {last_err}")

def analyze_ticker(ticker):
    try:
        dfd = fetch_daily(ticker)
        if dfd is None or dfd.empty or len(dfd) < 150:
            return {"ticker": ticker, "error": f"insufficient data {0 if dfd is None else len(dfd)}"}
        # clean
        dfd = dfd.dropna(subset=['Close'])
        if len(dfd) < 150:
            return {"ticker": ticker, "error": "too few closes after dropna"}

        dfd['atr'] = atr(dfd, config.ATR_LEN)
        dfd['atr_pct'] = dfd['atr'] / dfd['Close'] * 100
        dfd['vol_sma20'] = dfd['Volume'].rolling(20, min_periods=5).mean()
        dfd['rsi'] = rsi(dfd['Close'],14)

        last = dfd.iloc[-1]
        close = _safe_float(last.get('Close', np.nan))
        atr_v = _safe_float(last.get('atr', np.nan))
        atr_pct = _safe_float(last.get('atr_pct', np.nan))
        vol = _safe_float(last.get('Volume', 0))
        vol_sma = _safe_float(last.get('vol_sma20', np.nan))
        rsi_d = _safe_float(last.get('rsi', 50))

        if np.isnan(close) or np.isnan(atr_v) or atr_v <= 0:
            return {"ticker": ticker, "error": "nan close/atr"}

        # weekly breakout
        try:
            dfw_close = dfd['Close'].resample('W-FRI').last().dropna()
            dfw_high = dfd['High'].resample('W-FRI').max().dropna()
        except Exception:
            return {"ticker": ticker, "error": "weekly resample fail"}

        if len(dfw_close) < config.WEEKLY_LOOKBACK + 2:
            return {"ticker": ticker, "error": "not enough weeks"}

        # confirmed prior weeks high
        end_idx = -1  # last completed week is at -1 if today is weekend, else -2? use -2 to be safe for Friday close
        # use iloc[-2:-2-lookback] to avoid current incomplete week
        try:
            weekly_high = float(dfw_high.iloc[-2 - config.WEEKLY_LOOKBACK:-1].max())
        except Exception:
            weekly_high = float(dfw_high.iloc[-config.WEEKLY_LOOKBACK-1:-1].max())

        breakout = close > weekly_high
        near_breakout = close >= weekly_high * 0.985

        # monthly trend
        dfm = dfd['Close'].resample('ME').last().dropna()
        if len(dfm) >= 25:
            m_ef = ema(dfm, config.M_EMA_FAST)
            m_es = ema(dfm, config.M_EMA_SLOW)
            m_close = _safe_float(dfm.iloc[-1])
            m_ema_fast_v = _safe_float(m_ef.iloc[-1])
            m_ema_slow_v = _safe_float(m_es.iloc[-1])
            m_rsi_s = rsi(dfm,14)
            m_rsi = _safe_float(m_rsi_s.iloc[-1]) if len(m_rsi_s.dropna()) else 50
            m_trend = (m_close > m_ema_fast_v) and (m_ema_fast_v > m_ema_slow_v) and (m_rsi > 50)
        else:
            m_trend = False
            m_ema_fast_v = m_ema_slow_v = 0

        # quarterly / 3M momentum approx 63d
        if len(dfd) > 70:
            q_close = close
            q_ema63 = _safe_float(dfd['Close'].ewm(span=63, adjust=False).mean().iloc[-1])
            try:
                roc63 = (close / _safe_float(dfd['Close'].iloc[-64]) - 1) * 100
            except Exception:
                roc63 = 0
            rsi_series = rsi(dfd['Close'],14)
            q_rsi_val = _safe_float(rsi_series.iloc[-1], 50)
            q_mom = (q_close > q_ema63) and (q_rsi_val > config.Q_RSI_MIN) and (roc63 > config.Q_ROC_MIN)
        else:
            q_mom=False; roc63=0; q_rsi_val=rsi_d; q_ema63=close

        vol_crore = vol * close / 1e7
        vol_ok = (not np.isnan(vol_sma)) and vol > vol_sma * config.VOL_MULT
        volatility_ok = (not np.isnan(atr_pct)) and (config.MIN_ATR_PCT <= atr_pct <= config.MAX_ATR_PCT)
        rsi_ok = (not np.isnan(rsi_d)) and rsi_d > 50
        price_ok = close > 20  # lowered from 50 to allow more NSE stocks
        liquidity_ok = vol_crore >= 1  # relaxed for CI, filter later

        signal = breakout and m_trend and q_mom and vol_ok and volatility_ok and rsi_ok
        watch = near_breakout and m_trend and q_mom

        sl_price = close - atr_v * config.SL_ATR_MULT
        if sl_price <= 0 or sl_price >= close:
            sl_price = close * 0.97

        try:
            ps = position_size(close, sl_price)
        except Exception:
            ps = {"tp1": round(close*1.03,2), "tp2": round(close*1.07,2), "qty_final":0, "capital_used":0}

        return {
            "ticker": ticker,
            "symbol": ticker.replace(".NS","").replace(".BO",""),
            "close": round(close,2),
            "weekly_high": round(weekly_high,2),
            "breakout": bool(breakout),
            "near": bool(near_breakout),
            "m_trend": bool(m_trend),
            "q_mom": bool(q_mom),
            "q_roc63": round(roc63,1) if not np.isnan(roc63) else 0,
            "q_rsi": round(q_rsi_val,1) if not np.isnan(q_rsi_val) else 50,
            "atr_pct": round(atr_pct,2) if not np.isnan(atr_pct) else 0,
            "vol_x": round(vol/vol_sma,2) if vol_sma and vol_sma>0 else 0,
            "vol_cr": round(vol_crore,1),
            "rsi_d": round(rsi_d,1) if not np.isnan(rsi_d) else 50,
            "sl": round(sl_price,2),
            "risk_ps": round(close-sl_price,2),
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
        return {"ticker": ticker, "error": str(e)[:200]}

def scan_universe(save_json=True, mode=None, limit=None, delay=0.35):
    tickers, symbols = load_universe(mode=mode)
    if limit:
        tickers = tickers[:limit]
        symbols = symbols[:limit]
    results=[]; errors=[]
    for t in tqdm(tickers, desc="TDMB Scan", ncols=100):
        r = analyze_ticker(t)
        if r:
            if r.get("error"):
                errors.append(f"{t}: {r['error']}")
            else:
                results.append(r)
        # be nice to yahoo – important in CI
        time.sleep(delay + random.uniform(0,0.25))
        # occasional longer pause every 30 symbols
        if len(results) % 30 == 0 and len(results) > 0:
            time.sleep(1.5)
    # tiers
    signals = [x for x in results if x.get("signal")]
    watches = [x for x in results if x.get("watch") and not x.get("signal")]
    eligible_htf = [x for x in results if x.get("q_mom") and x.get("m_trend")]
    breakout_only = [x for x in results if x.get("breakout")]

    signals.sort(key=lambda x: (x["score"], x.get("vol_x",0), x.get("q_roc63",0)), reverse=True)
    watches.sort(key=lambda x: (x["score"], x.get("vol_x",0)), reverse=True)
    eligible_htf.sort(key=lambda x: (x.get("q_roc63",0), x.get("vol_x",0)), reverse=True)
    breakout_only.sort(key=lambda x: x.get("vol_x",0), reverse=True)

    try:
        regime, regime_info = get_nifty_regime()
    except Exception as e:
        regime = f"ERROR {e}"; regime_info = {}

    out = {
        "timestamp_ist": datetime.now(pytz.timezone(config.IST)).isoformat(),
        "regime": regime,
        "regime_info": regime_info,
        "signals": signals,
        "watchlist": watches,
        "eligible": eligible_htf,
        "breakout_only": breakout_only,
        "scanned": len(results),
        "errors": len(errors),
        "error_sample": errors[:10],
        "universe_mode": mode or config.UNIVERSE_MODE,
        "total_tickers": len(tickers)
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
    ap.add_argument("--delay", type=float, default=0.35, help="delay between tickers")
    args = ap.parse_args()
    res = scan_universe(mode=args.universe, limit=args.limit, delay=args.delay)
    print(f"Nifty Regime: {res['regime']}")
    print(f"Signals: {len(res['signals'])}  Watch: {len(res['watchlist'])}  Eligible HTF: {len(res['eligible'])}  Scanned {res['scanned']}/{res['total_tickers']}  Errors {res['errors']}")
    if res['error_sample']:
        print("Sample errors:", res['error_sample'][:3])
    print("\n--- BREAKOUT SIGNALS ---")
    for s in res["signals"][:20]:
        print(f"{s['symbol']:14} ₹{s['close']} > W12 {s['weekly_high']} | SL {s['sl']} | Qty {s['qty']} | Vol {s['vol_x']}x | ATR {s['atr_pct']}% | 3M {s['q_roc63']}%")
    if res["watchlist"]:
        print("\n--- WATCH NEAR BREAKOUT ---")
        for w in res["watchlist"][:10]:
            print(f"{w['symbol']:14} ₹{w['close']}/{w['weekly_high']}  Vol {w['vol_x']}x  3M {w['q_roc63']}%")
    if args.json:
        print(json.dumps(res, indent=2))

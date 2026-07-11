#!/usr/bin/env python3
import argparse, math
import config

def position_size(entry, sl, account=config.ACCOUNT_SIZE, risk_pct=config.RISK_PER_TRADE, max_pos_pct=config.MAX_POS_PCT):
    entry = float(entry)
    sl = float(sl)
    risk_per_share = abs(entry - sl)
    if risk_per_share <= 0:
        raise ValueError("SL must be < entry for long")
    risk_rupees = account * risk_pct / 100.0
    qty_risk = risk_rupees / risk_per_share
    capital_needed = qty_risk * entry
    cap_limit = account * max_pos_pct / 100.0
    qty_capped = min(qty_risk, cap_limit / entry)
    qty = math.floor(qty_capped)
    return {
        "entry": entry,
        "sl": sl,
        "risk_per_share": round(risk_per_share,2),
        "risk_rupees": round(risk_rupees,2),
        "qty_risk_based": math.floor(qty_risk),
        "qty_final": qty,
        "capital_used": round(qty * entry,2),
        "capital_needed_uncapped": round(capital_needed,2),
        "risk_pct_actual": round((qty * risk_per_share / account * 100), 3),
        "sl_pct": round(risk_per_share/entry*100,2),
        "tp1": round(entry + risk_per_share * config.TP1_R,2),
        "tp2": round(entry + risk_per_share * config.TP2_R,2),
        "capped": qty_capped < qty_risk
    }

def print_result(r):
    print(f"""
TDMB Position Sizer – ₹{config.ACCOUNT_SIZE:,.0f} acct | {config.RISK_PER_TRADE}% risk
Entry: ₹{r['entry']}  SL: ₹{r['sl']}  Risk/share: ₹{r['risk_per_share']} ({r['sl_pct']}%)
Risk Budget: ₹{r['risk_rupees']:,.0f}
Qty (risk-based): {r['qty_risk_based']}  → Capital ₹{r['capital_needed_uncapped']:,.0f}
Qty FINAL (cap {config.MAX_POS_PCT}%): {r['qty_final']}  {'⚠️ CAPPED' if r['capped'] else ''}
Capital Used: ₹{r['capital_used']:,.0f}
Actual Risk: ₹{r['qty_final']*r['risk_per_share']:,.0f} ({r['risk_pct_actual']}%)
TP1 {config.TP1_R}R: ₹{r['tp1']}  (sell 40%)
TP2 {config.TP2_R}R: ₹{r['tp2']}  (sell 30%)
Trail: Chandelier {config.TRAIL_ATR_MULT}ATR – 30%
""".strip())

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="TDMB Risk Calculator")
    ap.add_argument("--entry", "-e", type=float, required=True)
    ap.add_argument("--sl", "-s", type=float, required=True)
    ap.add_argument("--account", "-a", type=float, default=config.ACCOUNT_SIZE)
    ap.add_argument("--risk", "-r", type=float, default=config.RISK_PER_TRADE)
    args = ap.parse_args()
    # temporarily override
    config.ACCOUNT_SIZE = args.account
    config.RISK_PER_TRADE = args.risk
    res = position_size(args.entry, args.sl, args.account, args.risk)
    print_result(res)

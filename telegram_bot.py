#!/usr/bin/env python3
import os, json, asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import config
from scanner import scan_universe
from risk_calculator import position_size
from stock_universe import get_nifty_regime

def format_scan_message(data, long=False):
    """Build Telegram message(s). If long=True include eligible pool."""
    ist_time = data.get("timestamp_ist","")
    regime = data.get("regime","?")
    universe = data.get("universe_mode", config.UNIVERSE_MODE)
    scanned = data.get("scanned", 0)
    signals = data.get("signals", [])
    watch = data.get("watchlist", [])
    eligible = data.get("eligible", [])
    breakout_only = data.get("breakout_only", [])

    header = [
        f"🚀 TDMB WEEKLY BREAKOUT",
        f"{ist_time[:16].replace('T',' ')} IST | {universe}",
        f"NIFTY Regime: {regime}",
        f"Scanned: {scanned} | Signals: {len(signals)} | Watch: {len(watch)} | Eligible HTF: {len(eligible)}",
        ""
    ]
    # if short mode and no signals
    if not long and not signals:
        header.append("No fresh 12-week breakouts passing 3M+Monthly filters.")
    
    chunks = []
    current = header.copy()

    def flush():
        nonlocal current
        if current:
            chunks.append("\n".join(current))
            current = []

    # --- SIGNALS ---
    if signals and config.TELEGRAM_SEND_SIGNALS:
        current.append(f"🔥 BREAKOUTS ({len(signals)}):")
        current.append("")
        max_sig = config.TELEGRAM_MAX_SIGNALS if long else 8
        for i, s in enumerate(signals[:max_sig], 1):
            block = [
                f"{i}. {s['symbol']}",
                f"  ₹{s['close']} > 12W ₹{s['weekly_high']}",
                f"  3M: {'✅' if s['q_mom'] else '❌'} ROC {s['q_roc63']}% RSI {s['q_rsi']}  M: {'✅' if s['m_trend'] else '❌'}  Vol {s['vol_x']}x",
                f"  SL ₹{s['sl']} ({round((s['close']-s['sl'])/s['close']*100,1)}%)  ATR {s['atr_pct']}%",
                f"  TP1 ₹{s['tp1']}  TP2 ₹{s['tp2']}",
                f"  Qty {s['qty']} | ₹{s['capital']:,.0f}",
                ""
            ]
            # check size, flush if needed ~3500 chars
            if sum(len(l) for l in current) + sum(len(l) for l in block) > 3500:
                flush()
                current.append(f"🔥 BREAKOUTS cont.:")
                current.append("")
            current.extend(block)
        flush()

    # --- WATCHLIST ---
    if watch and config.TELEGRAM_SEND_WATCH:
        current = [f"👀 WATCH – Near 12W High ({len(watch)}):", ""]
        max_w = config.TELEGRAM_MAX_WATCH if long else 10
        for i, w in enumerate(watch[:max_w], 1):
            line = f"{i}. {w['symbol']} ₹{w['close']}/{w['weekly_high']}  Vol{w['vol_x']}x  ATR{w['atr_pct']}%  3M{w['q_roc63']}%  RSI{w['rsi_d']}"
            current.append(line)
            if sum(len(l) for l in current) > 3500:
                flush()
                current = [f"👀 WATCH cont.:", ""]
        current.append("")
        current.append(f"Risk/Trade ₹{config.RISK_RUPEES:,.0f} | /risk SYMBOL ENTRY SL")
        flush()

    # --- ELIGIBLE HTF POOL ---
    if long and eligible and config.TELEGRAM_SEND_ELIGIBLE:
        # filter out already in signals/watch to avoid duplicate
        sig_syms = {s['symbol'] for s in signals}
        watch_syms = {w['symbol'] for w in watch}
        pool = [e for e in eligible if e['symbol'] not in sig_syms and e['symbol'] not in watch_syms]
        if pool:
            current = [f"✅ ELIGIBLE HTF POOL – 3M+Monthly PASS ({len(pool)}):", "Top momentum sorted:", ""]
            max_e = config.TELEGRAM_MAX_ELIGIBLE
            for i, e in enumerate(pool[:max_e], 1):
                # compact line
                dist = round((e['close'] - e['weekly_high'])/e['weekly_high']*100,1)
                current.append(f"{i}. {e['symbol']} ₹{e['close']}  12W{e['weekly_high']} ({dist:+}%)  3M{e['q_roc63']}%  Vol{e['vol_x']}x  ATR{e['atr_pct']}%")
                if sum(len(l) for l in current) > 3500:
                    flush()
                    current = [f"✅ ELIGIBLE cont.:", ""]
            flush()

    # --- BREAKOUT ONLY (weak HTF) ---
    if long and breakout_only:
        # show top 10 that broke out but failed HTF – avoid trap
        weak = [b for b in breakout_only if b['symbol'] not in sig_syms][:10]
        if weak:
            current = ["⚠️ BREAKOUT NO HTF – avoid / wait:", ""]
            for w in weak:
                current.append(f"• {w['symbol']} ₹{w['close']}>{w['weekly_high']}  Q:{'Y' if w['q_mom'] else 'n'} M:{'Y' if w['m_trend'] else 'n'}")
            flush()

    if not chunks:
        # fallback – at least header
        chunks = ["\n".join(header + ["No signals today. Check /scan Monday."])]
    return chunks if long else chunks[0] if chunks else "\n".join(header)

async def send_messages(chat_id, messages):
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    try:
        for msg in messages:
            if msg.strip():
                await app.bot.send_message(chat_id=chat_id, text=msg[:4096])
                await asyncio.sleep(0.4)
    finally:
        await app.shutdown()

async def send_scan(chat_id=None, long=True):
    chat_id = chat_id or config.TELEGRAM_CHAT_ID
    if not config.TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN missing")
        return
    data = await asyncio.to_thread(scan_universe)
    msgs = format_scan_message(data, long=long)
    if isinstance(msgs, str):
        msgs = [msgs]
    await send_messages(chat_id, msgs)

async def send_long_message(data, chat_id=None):
    """Send already-scanned data in multiple chunks – ALL eligible"""
    chat_id = chat_id or config.TELEGRAM_CHAT_ID
    msgs = format_scan_message(data, long=True)
    if isinstance(msgs, str):
        msgs = [msgs]
    await send_messages(chat_id, msgs)

# --- Bot Commands ---
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "TDMB Bot live.\n"
        "/scan – Nifty500 full scan (~12 min)\n"
        "/scan200 – fast Nifty200\n"
        "/risk SYMBOL ENTRY SL\n"
        "/status\n"
        "/eligible – show HTF eligible pool"
    )

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = "NIFTY500"
    # allow /scan200
    if update.message.text.startswith("/scan200"):
        mode = "NIFTY200"
    await update.message.reply_text(f"Scanning {mode}… 2–15 min, will DM in parts.")
    data = await asyncio.to_thread(scan_universe, True, mode, None)
    msgs = format_scan_message(data, long=True)
    if isinstance(msgs, str):
        msgs = [msgs]
    for m in msgs:
        await update.message.reply_text(m[:4096])
        await asyncio.sleep(0.3)

async def cmd_eligible(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Fetching eligible HTF pool…")
    data = await asyncio.to_thread(scan_universe, True, "NIFTY500", None)
    eligible = data.get("eligible", [])[:30]
    lines = ["✅ ELIGIBLE – 3M + Monthly trend", ""]
    for i, e in enumerate(eligible, 1):
        lines.append(f"{i}. {e['symbol']} ₹{e['close']} | 3M {e['q_roc63']}% | W12 {e['weekly_high']} | Vol {e['vol_x']}x")
    txt = "\n".join(lines)
    for chunk_start in range(0, len(txt), 3900):
        await update.message.reply_text(txt[chunk_start:chunk_start+3900])

async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) < 3:
            await update.message.reply_text("Usage: /risk SYMBOL ENTRY SL\nExample: /risk RELIANCE 2980 2880")
            return
        sym, entry, sl = context.args[0], float(context.args[1]), float(context.args[2])
        ps = position_size(entry, sl)
        txt = (f"{sym.upper()}\nEntry ₹{entry} SL ₹{sl}\n"
               f"Risk/share ₹{ps['risk_per_share']} ({ps['sl_pct']}%)\n"
               f"Qty: {ps['qty_final']} {'(capped)' if ps['capped'] else ''}\n"
               f"Capital: ₹{ps['capital_used']:,.0f}\n"
               f"Risk: ₹{ps['qty_final']*ps['risk_per_share']:,.0f}\n"
               f"TP1 ₹{ps['tp1']}  TP2 ₹{ps['tp2']}")
        await update.message.reply_text(txt)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    regime, info = await asyncio.to_thread(get_nifty_regime)
    await update.message.reply_text(
        f"Nifty: {regime}\n{info}\n"
        f"Account ₹{config.ACCOUNT_SIZE:,.0f} | Risk {config.RISK_PER_TRADE}%\n"
        f"SL {config.SL_ATR_MULT}ATR | Trail {config.TRAIL_ATR_MULT}ATR\n"
        f"Universe: {config.UNIVERSE_MODE}"
    )

def run_bot():
    if not config.TELEGRAM_BOT_TOKEN:
        print("Set TELEGRAM_BOT_TOKEN in .env")
        return
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("scan200", cmd_scan))
    app.add_handler(CommandHandler("eligible", cmd_eligible))
    app.add_handler(CommandHandler("risk", cmd_risk))
    app.add_handler(CommandHandler("status", cmd_status))
    print("TDMB Telegram bot polling…")
    app.run_polling()

if __name__ == "__main__":
    import sys
    if "--send-once" in sys.argv:
        asyncio.run(send_scan(long=True))
    else:
        run_bot()

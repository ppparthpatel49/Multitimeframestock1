#!/usr/bin/env python3
import os, json, asyncio, html
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ParseMode
import config
from scanner import scan_universe
from risk_calculator import position_size
from stock_universe import get_nifty_regime

# ---- config ----
COMPACT = True  # short, mobile-friendly messages

def fmt(n, dec=2):
    try: return f"{float(n):,.{dec}f}".rstrip('0').rstrip('.')
    except: return str(n)

def fmt_inr_short(n):
    try:
        n=float(n)
        if n>=10000000: return f"{n/10000000:.2f}cr".rstrip('0').rstrip('.').replace('.00','')+"cr" if False else f"₹{n/10000000:.1f}cr"
        if n>=100000: return f"₹{n/100000:.1f}L"
        return f"₹{n:,.0f}"
    except: return str(n)

def esc(s): return html.escape(str(s), quote=False)

# ---------- builders – COMPACT ----------
def build_header_compact(data):
    ts = data.get("timestamp_ist","")[:16].replace("T"," ")
    regime = data.get("regime","?").replace("✅","").replace("⚠️","").replace("❌","").strip()
    regime_emoji = "🟢" if "BULL" in data.get("regime","") else "🟡" if "NEUTRAL" in data.get("regime","") else "🔴" if "BEAR" in data.get("regime","") else "⚪"
    sig = len(data.get("signals",[]))
    watch = len(data.get("watchlist",[]))
    elig = len(data.get("eligible",[]))
    scanned = data.get("scanned",0)
    uni = data.get("universe_mode", config.UNIVERSE_MODE)
    return (
f"<b>📊 TDMB Scan</b> • {esc(ts)} IST\n"
f"{regime_emoji} Nifty {esc(regime)} • {esc(uni)} • {scanned} scanned\n"
f"🚀 <b>{sig}</b> Break • 👀 {watch} Watch • ⭐ {elig} Eligible\n"
f"Risk {config.RISK_PER_TRADE}% = {fmt_inr_short(config.RISK_RUPEES)} | A/c {fmt_inr_short(config.ACCOUNT_SIZE)}"
    )

def build_signal_compact(s, i=None):
    sym = esc(s['symbol'])
    num = f"{i}. " if i else ""
    # one compact block – 4 lines
    close = s['close']; wh = s['weekly_high']; sl=s['sl']
    slp = round((close-sl)/close*100,1) if close else 0
    return (
f"{num}<b>{sym}</b> 🚀 BUY\n"
f"₹{fmt(close)} > ₹{fmt(wh)} | SL ₹{fmt(sl)} ({slp}%)\n"
f"TP {fmt(s['tp1'])} / {fmt(s['tp2'])} | Qty <b>{s['qty']}</b>\n"
f"{'✅' if s.get('q_mom') else '—'}3M {'✅' if s.get('m_trend') else '—'}M • Vol{s.get('vol_x',0)}x • ATR{s.get('atr_pct',0)}%"
    )

def build_watch_compact_list(watch_list, max_n=25):
    if not watch_list: return ""
    lines = [f"<b>👀 Watch – near breakout ({len(watch_list)})</b>"]
    for w in watch_list[:max_n]:
        gap = (w['close']-w['weekly_high'])/w['weekly_high']*100 if w['weekly_high'] else 0
        lines.append(
            f"• <b>{esc(w['symbol'])}</b> ₹{fmt(w['close'])} → ₹{fmt(w['weekly_high'])} <i>({gap:+.1f}%)</i> • 3M{w.get('q_roc63',0)}% • V{w.get('vol_x',0)}x"
        )
    if len(watch_list) > max_n:
        lines.append(f"<i>… +{len(watch_list)-max_n} more</i>")
    return "\n".join(lines)

def build_eligible_compact(eligible_list, signals, watch, max_n=30):
    sig_s = {s['symbol'] for s in signals}
    wat_s = {w['symbol'] for w in watch}
    pool = [e for e in eligible_list if e['symbol'] not in sig_s and e['symbol'] not in wat_s]
    if not pool:
        return ""
    lines = [f"<b>⭐ Eligible – 3M+Monthly ({len(pool)})</b>", "<i>Top momentum – wait breakout</i>"]
    for i, e in enumerate(pool[:max_n], 1):
        dist = (e['close']-e['weekly_high'])/e['weekly_high']*100 if e['weekly_high'] else 0
        lines.append(f"{i}. <b>{esc(e['symbol'])}</b> ₹{fmt(e['close'])}  3M{e.get('q_roc63',0)}%  {dist:+.1f}% to High")
    if len(pool) > max_n:
        lines.append(f"<i>… +{len(pool)-max_n} more – use /eligible</i>")
    return "\n".join(lines)

def format_scan_message(data, long=True):
    """Returns list of short, mobile-readable HTML messages"""
    signals = data.get("signals", [])
    watch = data.get("watchlist", [])
    eligible = data.get("eligible", [])

    msgs = []

    # Msg 1 – header + top breakouts (max 3)
    header = build_header_compact(data)
    body = [header, ""]
    if signals:
        body.append(f"<b>🚀 BREAKOUTS – Top {min(3, len(signals))} of {len(signals)}</b>")
        body.append("")
        for i, s in enumerate(signals[:3], 1):
            body.append(build_signal_compact(s, i))
            body.append("")  # blank line
        if len(signals) > 3:
            body.append(f"<i>… +{len(signals)-3} more breakout signals in next msg</i>")
    else:
        body.append("❌ <b>No confirmed breakout today</b>")
        body.append("Check Watchlist below 👇")
    msgs.append("\n".join(body).strip())

    # Msg 2 – remaining breakouts if any
    if len(signals) > 3:
        parts = []
        # 4 per message
        chunk_size = 4
        remaining = signals[3:]
        for start in range(0, min(len(remaining), config.TELEGRAM_MAX_SIGNALS-3), chunk_size):
            chunk = remaining[start:start+chunk_size]
            lines = [f"<b>🚀 Breakouts cont. {start+4}–{start+3+len(chunk)}</b>", ""]
            for j, s in enumerate(chunk, start+4):
                lines.append(build_signal_compact(s, j))
                lines.append("")
            msgs.append("\n".join(lines).strip())

    # Msg – Watchlist (compact)
    if watch and config.TELEGRAM_SEND_WATCH:
        # split watch into chunks of 18 lines (~1200 chars)
        max_per_msg = 18
        for start in range(0, min(len(watch), config.TELEGRAM_MAX_WATCH), max_per_msg):
            sub = watch[start:start+max_per_msg]
            title = "👀 Watch – Near 12W High" if start==0 else "👀 Watch cont."
            txt = f"<b>{title}</b>\n" + build_watch_compact_list(sub, max_n=99).split("\n",1)[1] if "\n" in build_watch_compact_list(sub) else build_watch_compact_list(sub)
            # actually build_watch_compact_list already includes title – simplify:
            txt = build_watch_compact_list(sub, max_n=99)
            # replace first line title if cont
            if start>0:
                txt = txt.replace("👀 Watch – Near 12W High", "👀 Watch cont.", 1)
            msgs.append(txt)

    # Msg – Eligible pool compact
    if long and eligible and config.TELEGRAM_SEND_ELIGIBLE:
        sig_syms = {s['symbol'] for s in signals}
        watch_syms = {w['symbol'] for w in watch}
        pool = [e for e in eligible if e['symbol'] not in sig_syms and e['symbol'] not in watch_syms]
        if pool:
            chunk_size = 22
            max_e = min(len(pool), config.TELEGRAM_MAX_ELIGIBLE)
            for start in range(0, max_e, chunk_size):
                sub = pool[start:start+chunk_size]
                # build simple list
                lines = [f"<b>⭐ Eligible {start+1}–{start+len(sub)} / {len(pool)}</b>", "<i>3M + Monthly ↑ – wait breakout</i>", ""]
                for k, e in enumerate(sub, start+1):
                    dist = (e['close']-e['weekly_high'])/e['weekly_high']*100 if e['weekly_high'] else 0
                    lines.append(f"{k}. <b>{esc(e['symbol'])}</b> ₹{fmt(e['close'])} • 3M{e.get('q_roc63',0)}% • {dist:+.1f}%")
                msgs.append("\n".join(lines))

    # fallback
    if not msgs:
        msgs = [build_header_compact(data) + "\n\n<i>No candidates today.</i>"]

    # ensure size < 4000
    final=[]
    for m in msgs:
        if len(m) <= 4000:
            final.append(m)
        else:
            # split roughly by lines
            lines = m.split("\n")
            cur=""; cur_len=0
            for ln in lines:
                if cur_len + len(ln) > 3700:
                    final.append(cur); cur=ln; cur_len=len(ln)
                else:
                    cur += ("\n" if cur else "") + ln
                    cur_len += len(ln)+1
            if cur: final.append(cur)
    return final

# ---------- sending ----------
async def send_messages(chat_id, messages):
    from telegram.request import HTTPXRequest
    from telegram.error import TimedOut, NetworkError, RetryAfter
    from telegram.ext import ApplicationBuilder
    from telegram.constants import ParseMode
    request = HTTPXRequest(connection_pool_size=8, read_timeout=30.0, write_timeout=30.0, connect_timeout=20.0, pool_timeout=15.0)
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).request(request).build()
    try:
        total = len(messages)
        for idx, msg in enumerate(messages, 1):
            if not msg or not msg.strip(): continue
            # add page footer only if multi-part
            footer = f"\n\n<i>📄 {idx}/{total}</i>" if total>1 else ""
            text = (msg + footer)[:4096]
            for attempt in range(4):
                try:
                    await app.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
                    break
                except RetryAfter as ra:
                    await asyncio.sleep(int(getattr(ra, 'retry_after', 3))+1)
                except (TimedOut, NetworkError, Exception) as e:
                    if attempt == 3:
                        print(f"Send failed part {idx}: {e}")
                        break
                    await asyncio.sleep(2+attempt*2)
            await asyncio.sleep(0.9)
    finally:
        await app.shutdown()

async def send_scan(chat_id=None, long=True):
    chat_id = chat_id or config.TELEGRAM_CHAT_ID
    if not config.TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN missing"); return []
    data = await asyncio.to_thread(scan_universe)
    msgs = format_scan_message(data, long=long)
    await send_messages(chat_id, msgs)
    return msgs

async def send_long_message(data, chat_id=None):
    chat_id = chat_id or config.TELEGRAM_CHAT_ID
    msgs = format_scan_message(data, long=True)
    await send_messages(chat_id, msgs)
    return msgs

# ---------- bot commands ----------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 <b>TDMB Bot</b>\n"
        "/scan – Nifty500\n"
        "/scan200 – fast\n"
        "/eligible – HTF pool\n"
        "/risk SYMBOL ENTRY SL\n"
        "/status",
        parse_mode=ParseMode.HTML
    )

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = "NIFTY200" if "200" in (update.message.text or "") else "NIFTY500"
    await update.message.reply_text(f"🔎 Scanning <b>{mode}</b>…\nYou’ll get short buy cards.", parse_mode=ParseMode.HTML)
    data = await asyncio.to_thread(scan_universe, True, mode, None)
    msgs = format_scan_message(data, long=True)
    for m in msgs:
        await update.message.reply_text(m[:4096], parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        await asyncio.sleep(0.5)

async def cmd_eligible(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Eligible pool…")
    data = await asyncio.to_thread(scan_universe, True, "NIFTY500", None)
    msgs = format_scan_message(data, long=True)
    # send last 1-2 messages which contain eligible
    for m in msgs[-2:]:
        await update.message.reply_text(m[:4096], parse_mode=ParseMode.HTML)

async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) < 3:
            await update.message.reply_text("Usage:\n<code>/risk RELIANCE 2980 2880</code>", parse_mode=ParseMode.HTML)
            return
        sym, entry, sl = context.args[0].upper(), float(context.args[1]), float(context.args[2])
        from risk_calculator import position_size
        ps = position_size(entry, sl)
        txt = (f"<b>{esc(sym)} – Risk Calc</b>\n"
               f"Entry ₹{entry} | SL ₹{sl} ({ps['sl_pct']}%)\n"
               f"Qty <b>{ps['qty_final']}</b> {'⚠️ capped' if ps['capped'] else ''} | Cap {fmt_inr_short(ps['capital_used'])}\n"
               f"Risk {fmt_inr_short(ps['qty_final']*ps['risk_per_share'])} | TP1 ₹{ps['tp1']} | TP2 ₹{ps['tp2']}")
        await update.message.reply_text(txt, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Error: {esc(e)}")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    regime, info = await asyncio.to_thread(get_nifty_regime)
    txt = (f"<b>TDMB Status</b>\n"
           f"Nifty: {esc(str(regime))}\n"
           f"💼 {fmt_inr_short(config.ACCOUNT_SIZE)} • {config.RISK_PER_TRADE}% = {fmt_inr_short(config.RISK_RUPEES)}\n"
           f"SL {config.SL_ATR_MULT} ATR • Trail {config.TRAIL_ATR_MULT} ATR\n"
           f"Universe <b>{config.UNIVERSE_MODE}</b>")
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

def run_bot():
    if not config.TELEGRAM_BOT_TOKEN:
        print("Set TELEGRAM_BOT_TOKEN in .env"); return
    from telegram.ext import ApplicationBuilder, CommandHandler
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(read_timeout=30, write_timeout=30, connect_timeout=20)
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).request(request).build()
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

#!/usr/bin/env python3
import os, json, asyncio, html
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ParseMode
import config
from scanner import scan_universe
from risk_calculator import position_size
from stock_universe import get_nifty_regime

# ---------- formatting helpers ----------
def fmt_inr(n):
    try:
        n = float(n)
        if n >= 10000000:
            return f"₹{n/10000000:.2f}cr"
        if n >= 100000:
            return f"₹{n/100000:.1f}L"
        return f"₹{n:,.0f}"
    except:
        return str(n)

def fmt_num(n, dec=2):
    try:
        return f"{float(n):,.{dec}f}"
    except:
        return str(n)

def esc(t):
    return html.escape(str(t), quote=False)

# ---------- message builders ----------
def build_header(data):
    ts = data.get("timestamp_ist","")[:16].replace("T"," ")
    regime = data.get("regime","?")
    universe = esc(data.get("universe_mode", config.UNIVERSE_MODE))
    scanned = data.get("scanned",0)
    total = data.get("total_tickers", scanned)
    sig = len(data.get("signals",[]))
    watch = len(data.get("watchlist",[]))
    elig = len(data.get("eligible",[]))
    lines = [
        f"<b>📊 TDMB – Top-Down Momentum Breakout</b>",
        f"📅 {esc(ts)} IST  •  🏛 {universe}",
        f"📈 Nifty: {esc(regime)}",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"✅ Scanned: {scanned}/{total}",
        f"🚀 Breakouts: <b>{sig}</b>   👀 Watch: {watch}   ⭐ Eligible: {elig}",
        f"",
        f"💼 A/c {fmt_inr(config.ACCOUNT_SIZE)}  •  Risk <b>{config.RISK_PER_TRADE}%</b> = {fmt_inr(config.RISK_RUPEES)}",
        f"🛡 SL {config.SL_ATR_MULT} ATR  •  🎯 TP1 {config.TP1_R}R 40%  •  TP2 {config.TP2_R}R 30%",
        f"🔄 Trail: Chandelier {config.TRAIL_ATR_MULT}ATR 22",
        f"",
        f"⏰ <b>Trade Monday 9:20–9:45 AM</b>",
    ]
    return "\n".join(lines)

def build_breakout_card(s, idx):
    sym = esc(s['symbol'])
    close = s['close']
    wh = s['weekly_high']
    sl = s['sl']
    risk_ps = s.get('risk_ps', close-sl)
    risk_pct = (close-sl)/close*100 if close else 0
    tp1 = s['tp1']; tp2 = s['tp2']
    qty = s['qty']; cap = s['capital']
    # recalc actual risk (capped)
    actual_risk = qty * risk_ps
    actual_r_pct = actual_risk / config.ACCOUNT_SIZE * 100

    # nice numbers
    def r(v): 
        return f"{v:,.2f}".rstrip('0').rstrip('.') if isinstance(v,(int,float)) else v

    card = f"""<b>{idx}️⃣ {sym} – BREAKOUT 🚀</b>
━━━━━━━━━━━━━━━━
🔔 <b>Entry</b>  : ₹{r(close)}
📊 Break : ₹{r(wh)}
🛡 <b>SL</b>     : ₹{r(sl)}  •  <b>{risk_pct:.1f}%</b>
📉 Risk  : ₹{r(risk_ps)}/share

🎯 <b>TP1</b> : ₹{r(tp1)}  +{config.TP1_R}R  <i>sell 40%</i>
🎯 <b>TP2</b> : ₹{r(tp2)}  +{config.TP2_R}R  <i>sell 30%</i>
🔄 Trail : Chandelier {config.TRAIL_ATR_MULT}ATR  <i>30%</i>

📦 <b>Qty</b>  : <b>{qty} shares</b>
💰 Cap  : {fmt_inr(cap)}  {'⚠️ capped 20%' if cap >= config.MAX_CAPITAL_PER_POS*0.99 else ''}
⚡ R-risk: {fmt_inr(actual_risk)}  ({actual_r_pct:.2f}%)

📈 <b>3M</b> : {'✅' if s.get('q_mom') else '❌'} ROC {s.get('q_roc63',0)}%  | RSI {s.get('q_rsi',0)}
📆 <b>Monthly</b> : {'✅ TREND' if s.get('m_trend') else '—'}
📊 Vol : <b>{s.get('vol_x',0)}x</b>  •  ATR {s.get('atr_pct',0)}%  •  RSI {s.get('rsi_d',0)}
💧 Liq : {s.get('vol_cr',0)} cr/day
"""
    return card

def build_watch_table(watch_list, title="👀 WATCHLIST – Near 12W High"):
    if not watch_list:
        return ""
    # build monospace table
    header = f"{title}\n<pre>"
    rows = ["SYMBOL       CLOSE → BRK     GAP    3M%   VOL  ATR"]
    rows.append("──────────────────────────────────────────────")
    for w in watch_list:
        sym = (w['symbol'][:12]).ljust(12)
        close = w['close']
        wh = w['weekly_high']
        gap = (close-wh)/wh*100
        line = f"{sym} {close:7.1f}→{wh:7.1f} {gap:+5.1f}% {w.get('q_roc63',0):5.1f} {w.get('vol_x',0):4.1f}x {w.get('atr_pct',0):4.1f}%"
        rows.append(line)
    footer = "</pre>\n<i>Buy on close above Break level, Vol &gt;1.25x</i>"
    return header + "\n".join(rows) + "\n" + footer

def build_eligible_table(eligible_list, title="⭐ ELIGIBLE – 3M + Monthly Trend"):
    if not eligible_list:
        return ""
    # remove duplicates already filtered by caller
    out = [f"<b>{title}</b>", f"<i>Top momentum – trade breakout only</i>", "<pre>"]
    out.append("#  SYMBOL       Price    3M%    12W High   Dist   Vol")
    out.append("──────────────────────────────────────────────────")
    for i, e in enumerate(eligible_list, 1):
        sym = e['symbol'][:12].ljust(12)
        dist = (e['close'] - e['weekly_high'])/e['weekly_high']*100 if e['weekly_high'] else 0
        out.append(f"{i:2d} {sym} {e['close']:7.1f} {e.get('q_roc63',0):6.1f}% {e['weekly_high']:9.1f} {dist:+5.1f}% {e.get('vol_x',0):4.1f}x")
    out.append("</pre>")
    return "\n".join(out)

def format_scan_message(data, long=True):
    """
    Returns list of HTML messages, each <3800 chars, clean readable.
    """
    # Part 1 – header / summary
    msgs = []
    header = build_header(data)
    signals = data.get("signals", [])
    watch = data.get("watchlist", [])
    eligible = data.get("eligible", [])
    breakout_only = data.get("breakout_only", [])

    # if no signals – still send clear message
    if not signals:
        no_sig = header + "\n\n" + "❌ <b>No fresh 12-week breakouts today passing 3M+Monthly+Vol filters.</b>\n\n👀 Check Watchlist & Eligible pool below – prepare for Monday."
        msgs.append(no_sig)

    # Breakout cards – 2 per message max for readability
    max_per_msg = 2
    if signals and config.TELEGRAM_SEND_SIGNALS:
        sig_limit = config.TELEGRAM_MAX_SIGNALS if long else 6
        chunk = []
        count = 0
        for i, s in enumerate(signals[:sig_limit], 1):
            chunk.append(build_breakout_card(s, i))
            count += 1
            if count % max_per_msg == 0 or i == min(sig_limit, len(signals)):
                body = "\n\n".join(chunk)
                # prepend a small header on first chunk
                if i <= max_per_msg:
                    body = f"<b>🚀 BREAKOUTS – {len(signals)} qualified</b>\n<i>Monday 9:20 AM execution</i>\n\n" + body
                msgs.append(body)
                chunk = []

    # Watchlist – 1 message table
    if watch and config.TELEGRAM_SEND_WATCH:
        max_w = config.TELEGRAM_MAX_WATCH if long else 12
        wt = build_watch_table(watch[:max_w])
        if wt:
            msgs.append(wt)

    # Eligible HTF pool
    if long and eligible and config.TELEGRAM_SEND_ELIGIBLE:
        # remove signal/watch duplicates
        sig_syms = {s['symbol'] for s in signals}
        watch_syms = {w['symbol'] for w in watch}
        pool = [e for e in eligible if e['symbol'] not in sig_syms and e['symbol'] not in watch_syms]
        if pool:
            # chunk eligible into 25 per message
            max_e = config.TELEGRAM_MAX_ELIGIBLE
            pool = pool[:max_e]
            chunk_size = 25
            for start in range(0, len(pool), chunk_size):
                sub = pool[start:start+chunk_size]
                title = "⭐ ELIGIBLE – 3M + Monthly Trend" if start==0 else "⭐ ELIGIBLE cont."
                msgs.append(build_eligible_table(sub, title))

    # Breakout no HTF – warning list compact
    if long and breakout_only:
        sig_syms = {s['symbol'] for s in signals}
        weak = [b for b in breakout_only if b['symbol'] not in sig_syms][:12]
        if weak:
            lines = ["<b>⚠️ BREAKOUT – NO HTF – Avoid / Wait</b>", "<pre>SYMBOL     Close > WkH   Q  M  Vol</pre>", ""]
            # use simple lines – avoid <pre> nesting issues
            txt_lines = []
            for w in weak:
                txt_lines.append(f"• {w['symbol']:<12} ₹{w['close']} > ₹{w['weekly_high']}  Q:{'Y' if w.get('q_mom') else 'n'} M:{'Y' if w.get('m_trend') else 'n'} Vol{w.get('vol_x',0)}x")
            lines.append("\n".join(txt_lines))
            msgs.append("\n".join(lines))

    # ensure first message always has header
    if msgs and not msgs[0].startswith("📊") and not "TDMB" in msgs[0][:30]:
        msgs[0] = header + "\n\n━━━━━━━━━━━━━━━━━━━━\n\n" + msgs[0]
    elif not msgs:
        msgs = [header + "\n\n<i>No candidates today.</i>"]

    # Telegram limit safety – split oversized
    final = []
    for m in msgs:
        if len(m) <= 4000:
            final.append(m)
        else:
            # hard split
            for i in range(0, len(m), 3800):
                final.append(m[i:i+3800])
    return final

# ---------- sending ----------
async def send_messages(chat_id, messages):
    from telegram.request import HTTPXRequest
    from telegram.error import TimedOut, NetworkError, RetryAfter
    request = HTTPXRequest(connection_pool_size=8, read_timeout=30.0, write_timeout=30.0, connect_timeout=20.0, pool_timeout=15.0)
    from telegram.ext import ApplicationBuilder
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).request(request).build()
    try:
        total = len(messages)
        for idx, msg in enumerate(messages, 1):
            if not msg or not msg.strip():
                continue
            # add page footer
            footer = f"\n\n<i>📄 {idx}/{total} • TDMB • {config.UNIVERSE_MODE}</i>" if total > 1 else ""
            text = (msg + footer)[:4096]
            for attempt in range(4):
                try:
                    await app.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                    break
                except RetryAfter as ra:
                    await asyncio.sleep(int(getattr(ra, 'retry_after', 5)) + 1)
                    continue
                except (TimedOut, NetworkError, Exception) as e:
                    if attempt == 3:
                        print(f"Telegram send failed part {idx}: {e}")
                        break
                    await asyncio.sleep(2 + attempt*3)
            await asyncio.sleep(1.0)
    finally:
        await app.shutdown()

async def send_scan(chat_id=None, long=True):
    chat_id = chat_id or config.TELEGRAM_CHAT_ID
    if not config.TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN missing")
        return []
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
        "📊 TDMB Bot\n"
        "/scan – Nifty500 full (~12 min)\n"
        "/scan200 – fast\n"
        "/eligible – HTF pool\n"
        "/risk SYMBOL ENTRY SL\n"
        "/status",
        parse_mode=ParseMode.HTML
    )

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = "NIFTY200" if update.message.text.startswith("/scan200") else "NIFTY500"
    await update.message.reply_text(f"🔎 Scanning <b>{mode}</b>…\nYou’ll get 2–4 formatted messages.\nETA 2–15 min.", parse_mode=ParseMode.HTML)
    data = await asyncio.to_thread(scan_universe, True, mode, None)
    msgs = format_scan_message(data, long=True)
    for m in msgs:
        await update.message.reply_text(m[:4096], parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        await asyncio.sleep(0.6)

async def cmd_eligible(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Fetching eligible HTF pool…")
    data = await asyncio.to_thread(scan_universe, True, "NIFTY500", None)
    msgs = format_scan_message(data, long=True)
    # send only eligible parts – messages 2+ usually contain pool, simplest send all
    for m in msgs:
        if "ELIGIBLE" in m or "WATCH" in m or "BREAKOUT" in m:
            await update.message.reply_text(m[:4096], parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.4)

async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) < 3:
            await update.message.reply_text("Usage:\n<code>/risk RELIANCE 2980 2880</code>", parse_mode=ParseMode.HTML)
            return
        sym, entry, sl = context.args[0].upper(), float(context.args[1]), float(context.args[2])
        ps = position_size(entry, sl)
        txt = (f"<b>{esc(sym)}</b>\n"
               f"Entry ₹{entry}  SL ₹{sl}\n"
               f"Risk/share ₹{ps['risk_per_share']}  ({ps['sl_pct']}%)\n"
               f"Qty: <b>{ps['qty_final']}</b> {'⚠️ capped' if ps['capped'] else ''}\n"
               f"Capital {fmt_inr(ps['capital_used'])}\n"
               f"Risk {fmt_inr(ps['qty_final']*ps['risk_per_share'])}\n"
               f"TP1 ₹{ps['tp1']}  •  TP2 ₹{ps['tp2']}")
        await update.message.reply_text(txt, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Error: {esc(e)}")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    regime, info = await asyncio.to_thread(get_nifty_regime)
    txt = (f"<b>TDMB Status</b>\n"
           f"Nifty: {esc(str(regime))}\n"
           f"{esc(str(info))}\n\n"
           f"💼 ₹{config.ACCOUNT_SIZE:,.0f}  •  Risk {config.RISK_PER_TRADE}%\n"
           f"🛡 SL {config.SL_ATR_MULT} ATR  •  Trail {config.TRAIL_ATR_MULT} ATR\n"
           f"🏛 Universe: <b>{config.UNIVERSE_MODE}</b>")
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

def run_bot():
    if not config.TELEGRAM_BOT_TOKEN:
        print("Set TELEGRAM_BOT_TOKEN in .env")
        return
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

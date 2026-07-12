from telegram import Bot
from telegram.constants import ParseMode
import asyncio
import config

def build_premium_signal(stock):
    """Build a compact 4-line premium buy signal."""
    reasons = " ".join([f"✅{r}" for r in stock['reasons']])
    return (
        f"<b>{stock['symbol']} [Score 3/3] 🚀</b>\n"
        f"Price: ₹{stock['price']:.2f} | RSI: {stock['rsi_d']:.1f}\n"
        f"Flags: {reasons}\n"
        f"Vol: {stock['vol_ratio']:.2f}x avg\n"
    )

def build_watchlist_item(stock):
    """Build a 1-line watchlist item."""
    reasons = "/".join(stock['reasons'])
    return f"🟡 {stock['symbol']} (2/3) - {reasons} | ₹{stock['price']:.2f}"

def build_exit_alert(trade):
    """Build a clear exit alert message."""
    color = "🔴" if trade['pnl_pct'] < 0 else "🟢"
    return (
        f"{color} <b>EXIT TRADE: {trade['symbol']}</b>\n"
        f"Entry: ₹{trade['entry_price']:.2f} $\rightarrow$ Exit: ₹{trade['exit_price']:.2f}\n"
        f"Result: <b>{trade['pnl_pct']:.2f}%</b>\n"
        f"Reason: {trade['reason']}"
    )

async def send_premium_report(bot, chat_id, data, exited_trades=[]):
    """Sends the full curated report including Exit Alerts."""
    msgs = []
    
    # 1. Exit Alerts First (Urgent)
    if exited_trades:
        exit_text = "🚨 <b>TRADE EXITS</b>\n\n"
        for t in exited_trades:
            exit_text += build_exit_alert(t) + "\n\n"
        msgs.append(exit_text)

    # 2. Header
    header = "🚀 <b>PREMIUM MOMENTUM SCAN</b>\n"
    header += f"Signals: {len(data['signals'])} | Watch: {len(data['watchlist'])}\n"
    header += "----------------------------------\n"
    msgs.append(header)

    # 3. Top Signals (3/3)
    if data['signals']:
        sig_text = "🔥 <b>TOP BUY SIGNALS (3/3)</b>\n\n"
        for s in data['signals'][:10]:
            sig_text += build_premium_signal(s) + "\n"
        msgs.append(sig_text)

    # 4. Watchlist (2/3)
    if data['watchlist']:
        watch_text = "🟡 <b>WATCHLIST (2/3)</b>\n"
        for s in data['watchlist'][:15]:
            watch_text += build_watchlist_item(s) + "\n"
        msgs.append(watch_text)

    for m in msgs:
        try:
            await bot.send_message(chat_id=chat_id, text=m, parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Telegram error: {e}")

from telegram import Bot
from telegram.constants import ParseMode
import asyncio
import config

def build_premium_signal(stock):
    """Build a compact 4-line premium buy signal."""
    reasons = " ".join([f"✅{r}" for r in stock['reasons']])
    return (
        f"<b>{stock['symbol']} [Score {stock['score']}/3] 🚀</b>\n"
        f"Price: ₹{stock['price']:.2f} | RSI: {stock['rsi_d']:.1f}\n"
        f"Flags: {reasons}\n"
        f"Vol: {stock['vol_ratio']:.2f}x avg\n"
    )

def build_watchlist_item(stock):
    """Build a 1-line watchlist item."""
    reasons = "/".join(stock['reasons'])
    return f"🟡 {stock['symbol']} ({stock['score']}/3) - {reasons} | ₹{stock['price']:.2f}"

def build_eligible_item(stock):
    """Build a 1-line eligible item."""
    return f"⚪ {stock['symbol']} (1/3) | ₹{stock['price']:.2f}"

async def send_premium_report(bot, chat_id, data):
    """Sends the final curated report to Telegram."""
    msgs = []
    
    # 1. Header
    header = "🚀 <b>PREMIUM MOMENTUM SCAN</b>\n"
    header += f"Signals: {len(data['signals'])} | Watch: {len(data['watchlist'])} | Pool: {len(data['eligible'])}\n"
    header += "----------------------------------\n"
    msgs.append(header)

    # 2. Top Signals (Score 3/3)
    if data['signals']:
        sig_text = "🔥 <b>TOP BUY SIGNALS (3/3)</b>\n\n"
        for s in data['signals'][:10]:
            sig_text += build_premium_signal(s) + "\n"
        msgs.append(sig_text)

    # 3. Watchlist (Score 2/3)
    if data['watchlist']:
        watch_text = "🟡 <b>WATCHLIST (2/3)</b>\n"
        for s in data['watchlist'][:15]:
            watch_text += build_watchlist_item(s) + "\n"
        msgs.append(watch_text)

    # 4. Eligible Pool (Score 1/3)
    if data['eligible']:
        pool_text = "⚪ <b>ELIGIBLE POOL (1/3)</b>\n"
        items = [build_eligible_item(s) for s in data['eligible']]
        for i in range(0, len(items), 20):
            pool_text += "\n".join(items[i:i+20]) + "\n"
        msgs.append(pool_text)

    # Send all messages
    for m in msgs:
        try:
            await bot.send_message(chat_id=chat_id, text=m, parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Telegram error: {e}")

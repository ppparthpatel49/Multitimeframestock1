import argparse
import asyncio
import datetime
import sys
from scanner import scan_universe
from telegram_bot import send_premium_report
from stock_universe import load_universe
import config
from telegram import Bot

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", type=str, default="nifty500")
    parser.add_argument("--chat-id", type=str, required=True)
    parser.add_argument("--token", type=str, required=True)
    args = parser.parse_args()

    # Load symbols from the universe manager
    symbols = load_universe(args.universe)
    
    if not symbols:
        print(f"❌ No symbols found for the selected universe: {args.universe}. Exiting.")
        return

    print(f"🚀 Starting Premium Scan for {args.universe} ({len(symbols)} stocks)...")
    
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    start_date = (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")

    data = scan_universe(symbols, start_date, end_date)

    bot = Bot(token=args.token)
    await send_premium_report(bot, args.chat_id, data)
    print(f"✅ Premium report for {args.universe} sent to Telegram!")

if __name__ == "__main__":
    asyncio.run(main())

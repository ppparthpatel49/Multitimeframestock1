import argparse
import asyncio
import datetime
import sys
import os
from scanner import scan_universe
from telegram_bot import send_premium_report
from stock_universe import load_universe
import portfolio_manager
import config
from telegram import Bot

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", type=str, default="nifty500")
    parser.add_argument("--chat-id", type=str, required=True)
    parser.add_argument("--token", type=str, required=True)
    args = parser.parse_args()
    portfolio_manager.init_files()
    symbols = load_universe(args.universe)
    if not symbols: return
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    start_date = (datetime.date.today() - datetime.timedelta(days=365*2)).strftime("%Y-%m-%d")
    data = scan_universe(symbols, start_date, end_date)
    from scanner import fetch_index_data
    index_close = fetch_index_data(config.INDEX_SYMBOL, start_date, end_date)
    exited_trades, current_portfolio = portfolio_manager.check_exits(index_close)
    for s in data['signals']: portfolio_manager.add_trade(s['symbol'], s['price'])
    bot = Bot(token=args.token)
    await send_premium_report(bot, args.chat_id, data, exited_trades)
if __name__ == "__main__":
    asyncio.run(main())

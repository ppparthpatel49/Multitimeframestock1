#!/usr/bin/env python3
import argparse, asyncio, json, os
from scanner import scan_universe
from telegram_bot import send_scan, format_scan_message, send_long_message

def print_messages(msgs):
    if isinstance(msgs, list):
        for i, m in enumerate(msgs, 1):
            print(f"\n===== PART {i}/{len(msgs)} =====\n")
            print(m)
    else:
        print(msgs)

def main():
    ap = argparse.ArgumentParser(description="TDMB Top-Down Momentum Breakout")
    ap.add_argument("--scan", action="store_true", help="Run scanner now")
    ap.add_argument("--send", action="store_true", help="Send Telegram after scan – ALL eligible")
    ap.add_argument("--send-last", action="store_true", help="Resend last_scan.json")
    ap.add_argument("--chat-id", type=str, default=None)
    ap.add_argument("--universe", "-u", choices=["NIFTY500","NIFTY200","CUSTOM"], default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--all", action="store_true", help="Force send ALL eligible candidates (default on)")
    args = ap.parse_args()

    if args.send_last:
        if os.path.exists("output/last_scan.json"):
            with open("output/last_scan.json") as f:
                data = json.load(f)
            msgs = format_scan_message(data, long=True)
            print_messages(msgs)
            if args.send:
                asyncio.run(send_long_message(data, args.chat_id))
        else:
            print("No output/last_scan.json found. Run --scan first.")
        return

    if args.scan or args.send or not (args.scan or args.send or args.send_last):
        data = scan_universe(mode=args.universe, limit=args.limit)
        msgs = format_scan_message(data, long=True)
        print_messages(msgs)
        if args.send:
            asyncio.run(send_long_message(data, args.chat_id))

if __name__ == "__main__":
    main()


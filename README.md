# TDMB Python – Telegram Weekly Breakout Scanner

Quick start:

```bash
pip install -r requirements.txt
cp .env.example .env
# edit TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
# edit universe.csv – add your NSE symbols (no .NS)

python risk_calculator.py -e 2980 -s 2880
python scanner.py
python main.py --scan --send
```

Bot commands:
- /scan
- /risk SYMBOL ENTRY SL
- /status

Cron (IST):
```
50 9 * * 5 cd /path/topdown-trader/python && python3 main.py --scan --send
30 4 * * 0 cd /path/topdown-trader/python && python3 main.py --send-last
```

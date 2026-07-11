import os
from dotenv import load_dotenv
load_dotenv()

ACCOUNT_SIZE = float(os.getenv("ACCOUNT_SIZE", 1000000))
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", 2.0))
MAX_POS_PCT = float(os.getenv("MAX_POS_PCT", 20.0))

SL_ATR_MULT = float(os.getenv("SL_ATR_MULT", 1.8))
TRAIL_ATR_MULT = float(os.getenv("TRAIL_ATR_MULT", 3.0))
TP1_R = 1.5
TP2_R = 3.5

WEEKLY_LOOKBACK = int(os.getenv("WEEKLY_LOOKBACK", 12))
ATR_LEN = 14
MIN_ATR_PCT = float(os.getenv("MIN_ATR_PCT", 1.5))
MAX_ATR_PCT = float(os.getenv("MAX_ATR_PCT", 6.0))
VOL_MULT = 1.25
MIN_VOLUME_CRORE = float(os.getenv("MIN_VOLUME_CRORE", 10))

Q_RSI_MIN = 55
Q_ROC_MIN = 8.0
M_EMA_FAST = 10
M_EMA_SLOW = 20

# Universe selection: NIFTY500 | NIFTY200 | CUSTOM
UNIVERSE_MODE = os.getenv("UNIVERSE_MODE", "NIFTY500")
UNIVERSE_FILE = os.getenv("UNIVERSE_FILE", "universe.csv")
NIFTY500_FILE = os.getenv("NIFTY500_FILE", "nifty500.csv")
REGIME_SYMBOL = os.getenv("REGIME_SYMBOL", "^NSEI")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Telegram output controls – send ALL eligible candidates
TELEGRAM_SEND_SIGNALS = True
TELEGRAM_SEND_WATCH = True
TELEGRAM_SEND_ELIGIBLE = True
TELEGRAM_MAX_SIGNALS = int(os.getenv("TELEGRAM_MAX_SIGNALS", 20))
TELEGRAM_MAX_WATCH = int(os.getenv("TELEGRAM_MAX_WATCH", 20))
TELEGRAM_MAX_ELIGIBLE = int(os.getenv("TELEGRAM_MAX_ELIGIBLE", 30))

IST = "Asia/Kolkata"

# Derived
RISK_RUPEES = ACCOUNT_SIZE * RISK_PER_TRADE / 100.0
MAX_CAPITAL_PER_POS = ACCOUNT_SIZE * MAX_POS_PCT / 100.0

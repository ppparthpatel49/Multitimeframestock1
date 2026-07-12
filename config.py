# Strategy Constants
RSI_LEN = 14
RSI_THRESHOLD = 50
EXIT_RSI_THRESHOLD = 40 # Exit when Daily RSI drops below this

# Relative Strength (RS)
RS_LOOKBACK = 63 # 3 Months
INDEX_SYMBOL = "^NSEI"

# Volume Footprint
VOL_SMA_LEN = 20
VOL_MULT = 1.2

# Risk Management
STOP_LOSS_PCT = 0.10 # 10% Hard Stop Loss

# File Paths (Root Folder)
LIVE_TRADES_FILE = "live_trades.csv"
TRADE_JOURNAL_FILE = "trade_journal.csv"

# Telegram Settings
TELEGRAM_MAX_SIGNALS = 20
TELEGRAM_SEND_SIGNALS = True
TELEGRAM_SEND_WATCH = True

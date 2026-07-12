# Strategy Constants
RSI_LEN = 14
RSI_THRESHOLD = 50
EXIT_RSI_THRESHOLD = 40

# Relative Strength (RS)
RS_LOOKBACK = 63 
INDEX_SYMBOL = "^NSEI"

# Volume Footprint
VOL_SMA_LEN = 20
VOL_MULT = 1.2 # Restored to 1.2 to strictly follow Institutional Effort spec

# Risk Management
STOP_LOSS_PCT = 0.10

# File Paths
LIVE_TRADES_FILE = "live_trades.csv"
TRADE_JOURNAL_FILE = "trade_journal.csv"

# Telegram Settings
MIN_SCORE_FOR_ALERT = 2 # Now sends 2/3 and 3/3 signals
TELEGRAM_MAX_SIGNALS = 20
TELEGRAM_SEND_SIGNALS = True
TELEGRAM_SEND_WATCH = True

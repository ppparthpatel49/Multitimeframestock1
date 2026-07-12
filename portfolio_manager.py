import pandas as pd
import os
import datetime
import yfinance as yf
from pandas_ta import rsi
import config

def init_files():
    if not os.path.exists(config.LIVE_TRADES_FILE):
        pd.DataFrame(columns=['symbol', 'entry_price', 'entry_date']).to_csv(config.LIVE_TRADES_FILE, index=False)
    if not os.path.exists(config.TRADE_JOURNAL_FILE):
        pd.DataFrame(columns=['symbol', 'entry_price', 'entry_date', 'exit_price', 'exit_date', 'pnl_pct']).to_csv(config.TRADE_JOURNAL_FILE, index=False)

def add_trade(symbol, price):
    df = pd.read_csv(config.LIVE_TRADES_FILE)
    if symbol not in df['symbol'].values:
        new_trade = pd.DataFrame([{'symbol': symbol, 'entry_price': price, 'entry_date': datetime.date.today().strftime("%Y-%m-%d")}])
        df = pd.concat([df, new_trade], ignore_index=True)
        df.to_csv(config.LIVE_TRADES_FILE, index=False)
        return True
    return False

def check_exits(index_close):
    df_live = pd.read_csv(config.LIVE_TRADES_FILE)
    if df_live.empty: return [], []
    exited_trades, still_live = [], []
    for _, trade in df_live.iterrows():
        symbol = trade['symbol']
        entry_price = trade['entry_price']
        try:
            df = yf.download(f"{symbol}.NS", period="6mo", progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            curr_price = df['Close'].iloc[-1]
            curr_rsi = rsi(df['Close'], length=config.RSI_LEN).iloc[-1]
            sl_hit = curr_price <= (entry_price * (1 - config.STOP_LOSS_PCT))
            rsi_exit = curr_rsi < config.EXIT_RSI_THRESHOLD
            if sl_hit or rsi_exit:
                exited_trades.append({'symbol': symbol, 'entry_price': entry_price, 'entry_date': trade['entry_date'], 'exit_price': curr_price, 'exit_date': datetime.date.today().strftime("%Y-%m-%d"), 'pnl_pct': ((curr_price - entry_price)/entry_price)*100, 'reason': "STOP LOSS" if sl_hit else "RSI TREND"})
            else: still_live.append(trade)
        except: still_live.append(trade)
    pd.DataFrame(still_live).to_csv(config.LIVE_TRADES_FILE, index=False)
    if exited_trades:
        df_journal = pd.read_csv(config.TRADE_JOURNAL_FILE)
        df_exited = pd.DataFrame(exited_trades).drop(columns=['reason'])
        df_journal = pd.concat([df_journal, df_exited], ignore_index=True)
        df_journal.to_csv(config.TRADE_JOURNAL_FILE, index=False)
    return exited_trades, still_live

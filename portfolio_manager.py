import pandas as pd
import os
import datetime
import config

def init_files():
    """Initialize CSV files if they don't exist."""
    if not os.path.exists(config.LIVE_TRADES_FILE):
        df = pd.DataFrame(columns=['symbol', 'entry_price', 'entry_date'])
        df.to_csv(config.LIVE_TRADES_FILE, index=False)
    
    if not os.path.exists(config.TRADE_JOURNAL_FILE):
        df = pd.DataFrame(columns=['symbol', 'entry_price', 'entry_date', 'exit_price', 'exit_date', 'pnl_pct'])
        df.to_csv(config.TRADE_JOURNAL_FILE, index=False)

def add_trade(symbol, price):
    """Add a new 3/3 trade to the live sheet."""
    df = pd.read_csv(config.LIVE_TRADES_FILE)
    if symbol not in df['symbol'].values:
        new_trade = pd.DataFrame([{
            'symbol': symbol, 
            'entry_price': price, 
            'entry_date': datetime.date.today().strftime("%Y-%m-%d")
        }])
        df = pd.concat([df, new_trade], ignore_index=True)
        df.to_csv(config.LIVE_TRADES_FILE, index=False)
        return True
    return False

def check_exits(index_close):
    """Check live trades for SL or RSI exit criteria."""
    df_live = pd.read_csv(config.LIVE_TRADES_FILE)
    if df_live.empty:
        return [], []

    exited_trades = []
    still_live = []
    
    import yfinance as yf
    from pandas_ta import rsi

    for _, trade in df_live.iterrows():
        symbol = trade['symbol']
        entry_price = trade['entry_price']
        
        try:
            # Fetch latest data
            df = yf.download(f"{symbol}.NS", period="6mo", progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            curr_price = df['Close'].iloc[-1]
            curr_rsi = rsi(df['Close'], length=config.RSI_LEN).iloc[-1]
            
            # Exit Logic
            sl_hit = curr_price <= (entry_price * (1 - config.STOP_LOSS_PCT))
            rsi_exit = curr_rsi < config.EXIT_RSI_THRESHOLD
            
            if sl_hit or rsi_exit:
                reason = "STOP LOSS" if sl_hit else "RSI TREND REVERSAL"
                pnl = (curr_price - entry_price) / entry_price
                
                exited_trades.append({
                    'symbol': symbol,
                    'entry_price': entry_price,
                    'entry_date': trade['entry_date'],
                    'exit_price': curr_price,
                    'exit_date': datetime.date.today().strftime("%Y-%m-%d"),
                    'pnl_pct': pnl * 100,
                    'reason': reason
                })
            else:
                still_live.append(trade)
                
        except Exception as e:
            print(f"Error checking exit for {symbol}: {e}")
            still_live.append(trade)

    # Update Live Sheet
    pd.DataFrame(still_live).to_csv(config.LIVE_TRADES_FILE, index=False)
    
    # Move to Journal
    if exited_trades:
        df_journal = pd.read_csv(config.TRADE_JOURNAL_FILE)
        df_exited = pd.DataFrame(exited_trades).drop(columns=['reason'])
        df_journal = pd.concat([df_journal, df_exited], ignore_index=True)
        df_journal.to_csv(config.TRADE_JOURNAL_FILE, index=False)

    return exited_trades, still_live

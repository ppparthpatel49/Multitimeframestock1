"""Quick walk-forward sanity check – not full backtest. Use Pine Strategy Tester for real backtest."""
import yfinance as yf, pandas as pd
from scanner import ema, rsi, atr
import config

ticker="RELIANCE.NS"
df = yf.download(ticker, period="5y", interval="1d", auto_adjust=True)
df['ema63']=ema(df['Close'],63)
df['rsi']=rsi(df['Close'])
df['atr']=atr(df,14)
# weekly high
weekly_high = df['High'].resample('W-FRI').max().reindex(df.index, method='ffill').shift(5*12)
entries = (df['Close'] > weekly_high) & (df['Close'].shift(1) <= weekly_high.shift(1))
trades = df[entries]
print(trades[['Close']].tail(20))
print(f"Raw breakout signals 5y: {entries.sum()} – filter further with monthly/quarterly in Pine.")

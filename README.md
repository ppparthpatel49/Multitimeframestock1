# 🚀 TDMB Premium Momentum System

A high-conviction stock scanning system for NSE India that combines **Multi-Timeframe RSI**, **Relative Strength (RS)**, and **Institutional Volume Footprints**.

## 🎯 The Strategy (The 3/3 Rule)
A stock is only flagged as a **PREMIUM BUY** when it hits a score of 3/3:
1. **MTF-RSI Alignment (✅ Trend):** Daily, Weekly, and Monthly RSI must all be above 50.
2. **Relative Strength (✅ Leadership):** The stock must be outperforming the Nifty 50 Index.
3. **Volume Footprint (✅ Big Money):** Price must rise on volume $> 1.2\text{x}$ the 20-day average.

## 🛠️ Setup Instructions

### 1. TradingView Setup
- Copy the code from `pine/TDMB_Premium_MTF.pine`.
- Open **TradingView** $\rightarrow$ **Pine Editor** $\rightarrow$ **Paste** $\rightarrow$ **Add to Chart**.

### 2. GitHub Setup (Automation)
- Create a new private repository on GitHub.
- Upload all files from this project.
- Go to **Settings** $\rightarrow$ **Secrets and Variables** $\rightarrow$ **Actions**.
- Add the following **Repository Secrets**:
  - `TELEGRAM_BOT_TOKEN`: Your BotFather token.
  - `TELEGRAM_CHAT_ID`: Your unique chat ID.

### 3. Trading Plan
- **Entry:** Buy when the bot sends a `3/3 Premium Signal`.
- **Stop Loss:** Low of the breakout candle or 10% below entry.
- **Exit:** 
  - Partial profit when Daily RSI > 75.
  - Full exit when Daily RSI < 40 or RS Line drops below its SMA.

## 📜 License
MIT

# BTC Perpetual Futures Trading Bot & Backtester

A quantitative, production-ready framework for trading Bitcoin Perpetual Futures with leverage, backtesting against real historical exchange data, and executing automated paper/live orders.

---

## 📁 Project Structure

```
btc_futures_bot/
├── data/
│   └── btc_futures_1h.csv       # 1-hour real historical BTC futures candles
├── strategies/
│   ├── base_strategy.py         # Abstract base class for all strategies
│   ├── ema_crossover.py         # Trend following EMA cross with 200 EMA filter
│   ├── rsi_bollinger.py         # Mean reversion with RSI and Bollinger Bands
│   └── atr_breakout.py          # Volatility channel breakout with ATR dynamic SL
├── results/
│   ├── backtest_EMA_12_26_5x.png
│   ├── backtest_RSI_Bollinger_MeanReversion_5x.png
│   ├── backtest_ATR_Breakout_24_5x.png
│   ├── strategy_comparison_summary.csv
│   └── trades_*.csv             # Granular trade-by-trade logs
├── data_loader.py               # Fetches real historical data via CCXT
├── backtester.py                # Perpetual futures simulation engine (fees, leverage, liq)
├── visualizer.py                # High-res chart generator (dark TradingView style)
├── run_backtest.py              # CLI comparison runner across strategies & leverage
└── live_bot.py                  # Paper trading / Live execution bot with testnet support
```

---

## 🚀 Getting Started

### 1. Activate Environment
```bash
cd /Users/martin.olariaga/.gemini/antigravity/scratch/btc_futures_bot
source venv/bin/activate
```

### 2. Download Real Historical Data
```bash
python3 data_loader.py
```
*Pulls real 1-hour OHLCV candles directly from Binance Perpetual Futures (`BTC/USDT:USDT`).*

### 3. Run Strategy Backtests & Benchmark
```bash
python3 run_backtest.py
```
*Tests EMA Crossover, RSI Bollinger Mean Reversion, and ATR Breakout across 2x, 5x, and 10x leverage levels. Generates performance comparison tables, visual charts, and trade logs in `results/`.*

### 4. Run the Live Paper Trading Bot
```bash
python3 live_bot.py
```
*Polls live BTC futures market data, computes signals, calculates leveraged position sizes, and logs paper orders with attached Stop Loss and Take Profit levels.*

---

## ⚙️ Perpetual Futures Specifics Simulated
- **Leveraged Taker/Maker Fees:** 0.05% taker / 0.02% maker applied to **notional value** ($Margin \times Leverage$).
- **Maintenance Margin & Liquidation:** Simulates exchange maintenance margin ($0.5\%$) and tracks intrabar liquidation triggers.
- **Funding Rate Cost of Carry:** Simulates standard 8-hour funding rate payments.
- **Slippage Modeling:** $0.03\%$ adverse execution penalty on entries/exits.

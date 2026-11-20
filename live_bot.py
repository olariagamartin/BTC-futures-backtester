import os
import time
import ccxt
import pandas as pd
from datetime import datetime, timezone
from strategies.ema_crossover import EMACrossoverStrategy

class BTCFuturesBot:
    """
    Automated Execution Bot for BTC Perpetual Futures.
    Supports:
    - Dry Run / Paper Trading Mode (Zero risk)
    - Binance / Bybit Futures Testnet & Live APIs
    - Automated Leverage Configuration
    - Position Sizing & Stop Loss order placement
    """
    def __init__(
        self,
        strategy,
        exchange_id: str = "binance",
        symbol: str = "BTC/USDT:USDT",
        timeframe: str = "1h",
        leverage: int = 3,
        trade_amount_usdt: float = 100.0,
        testnet: bool = True,
        dry_run: bool = True,
        api_key: str = "",
        api_secret: str = ""
    ):
        self.strategy = strategy
        self.exchange_id = exchange_id
        self.symbol = symbol
        self.timeframe = timeframe
        self.leverage = leverage
        self.trade_amount_usdt = trade_amount_usdt
        self.testnet = testnet
        self.dry_run = dry_run

        # Initialize CCXT exchange client
        exchange_class = getattr(ccxt, exchange_id)
        config = {
            'apiKey': api_key or os.getenv('EXCHANGE_API_KEY', ''),
            'secret': api_secret or os.getenv('EXCHANGE_SECRET', ''),
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        }
        self.exchange = exchange_class(config)
        
        if self.testnet:
            self.exchange.set_sandbox_mode(True)
            print(f"[INIT] Configured in SANDBOX / TESTNET mode on {exchange_id}")

        if self.dry_run:
            print("[INIT] DRY RUN ENABLED: No real orders will be sent to the exchange.")

    def set_up_leverage(self):
        """Sets the account leverage on the perpetual futures market."""
        if self.dry_run:
            print(f"[DRY RUN] Set leverage to {self.leverage}x for {self.symbol}")
            return
        try:
            res = self.exchange.set_leverage(self.leverage, self.symbol)
            print(f"[EXCHANGE] Leverage set to {self.leverage}x: {res}")
        except Exception as e:
            print(f"[WARNING] Could not set leverage via API: {e}")

    def fetch_latest_data(self, limit: int = 250) -> pd.DataFrame:
        """Fetches the latest OHLCV candles to evaluate the strategy."""
        candles = self.exchange.fetch_ohlcv(self.symbol, timeframe=self.timeframe, limit=limit)
        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        return df

    def get_current_position(self) -> dict:
        """Returns current open contracts and position side."""
        if self.dry_run:
            return {'side': 'flat', 'contracts': 0.0, 'entry_price': 0.0}

        try:
            positions = self.exchange.fetch_positions([self.symbol])
            for pos in positions:
                if pos['symbol'] == self.symbol:
                    contracts = float(pos.get('contracts', 0) or 0)
                    side = pos.get('side', 'flat') # 'long', 'short', 'flat'
                    entry_p = float(pos.get('entryPrice', 0) or 0)
                    return {'side': side, 'contracts': contracts, 'entry_price': entry_p}
        except Exception as e:
            print(f"[ERROR] Fetching positions failed: {e}")
        return {'side': 'flat', 'contracts': 0.0, 'entry_price': 0.0}

    def execute_signal(self, signal: int, current_price: float, sl_pct: float = 0.02, tp_pct: float = 0.05):
        """
        Executes order logic based on signal (1 = Long, -1 = Short, 0 = Close).
        """
        notional_target = self.trade_amount_usdt * self.leverage
        contracts = round(notional_target / current_price, 3)

        if signal == 1:
            print(f"\n[ACTION] GO LONG {self.symbol}")
            print(f"  Price: ${current_price:,.2f} | Leverage: {self.leverage}x | Size: {contracts} BTC (${notional_target:.2f})")
            sl_price = current_price * (1.0 - sl_pct)
            tp_price = current_price * (1.0 + tp_pct)
            print(f"  Stop Loss: ${sl_price:,.2f} (-{sl_pct*100:.1f}%) | Take Profit: ${tp_price:,.2f} (+{tp_pct*100:.1f}%)")

            if not self.dry_run:
                # Send Market Buy order
                order = self.exchange.create_market_buy_order(self.symbol, contracts)
                print(f"[ORDER PLACED] Market Long: {order['id']}")
                # Place Stop Loss Market
                sl_order = self.exchange.create_order(
                    self.symbol, 'stop_market', 'sell', contracts, 
                    params={'stopPrice': sl_price, 'reduceOnly': True}
                )
                print(f"[STOP LOSS PLACED] {sl_order['id']} at ${sl_price}")

        elif signal == -1:
            print(f"\n[ACTION] GO SHORT {self.symbol}")
            print(f"  Price: ${current_price:,.2f} | Leverage: {self.leverage}x | Size: {contracts} BTC (${notional_target:.2f})")
            sl_price = current_price * (1.0 + sl_pct)
            tp_price = current_price * (1.0 - tp_pct)
            print(f"  Stop Loss: ${sl_price:,.2f} (-{sl_pct*100:.1f}%) | Take Profit: ${tp_price:,.2f} (+{tp_pct*100:.1f}%)")

            if not self.dry_run:
                # Send Market Sell order
                order = self.exchange.create_market_sell_order(self.symbol, contracts)
                print(f"[ORDER PLACED] Market Short: {order['id']}")
                # Place Stop Loss Market
                sl_order = self.exchange.create_order(
                    self.symbol, 'stop_market', 'buy', contracts,
                    params={'stopPrice': sl_price, 'reduceOnly': True}
                )
                print(f"[STOP LOSS PLACED] {sl_order['id']} at ${sl_price}")

    def run_tick(self):
        """Single polling cycle for the bot."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"\n[{now_str}] Polling {self.symbol}...")
        df = self.fetch_latest_data()
        
        # Run strategy signals
        df_strat = self.strategy.generate_signals(df)
        last_closed_candle = df_strat.iloc[-2] # Last completed candle
        current_candle = df_strat.iloc[-1]     # Live incomplete candle

        signal = last_closed_candle['signal']
        curr_price = current_candle['close']
        sl_pct = last_closed_candle.get('sl_pct', 0.02)
        tp_pct = last_closed_candle.get('tp_pct', 0.05)

        print(f"  BTC Current Price: ${curr_price:,.2f}")
        print(f"  Strategy ({self.strategy.name}) Signal: {signal} (1=Long, -1=Short, 0=Neutral)")

        pos = self.get_current_position()
        print(f"  Current Position: {pos['side'].upper()} ({pos['contracts']} BTC)")

        # Trigger trade if signal requires action
        if signal != 0:
            self.execute_signal(signal, curr_price, sl_pct, tp_pct)
        else:
            print("  No trade condition met. Monitoring next candle...")

if __name__ == "__main__":
    # Test run a single tick in dry-run mode
    strat = EMACrossoverStrategy(fast_period=12, slow_period=26, trend_filter_period=200)
    bot = BTCFuturesBot(
        strategy=strat,
        exchange_id="binance",
        symbol="BTC/USDT:USDT",
        timeframe="1h",
        leverage=3,
        trade_amount_usdt=500.0,
        dry_run=True # Paper trading
    )
    bot.set_up_leverage()
    bot.run_tick()

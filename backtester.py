import pandas as pd
import numpy as np
from datetime import datetime

class PerpetualFuturesBacktester:
    """
    High-fidelity Perpetual Futures Backtesting Engine with:
    - Isolated Leverage (1x to 50x)
    - Maintenance margin & Liquidation price simulation
    - Taker/Maker fees applied to leveraged notional position
    - Slippage modeling
    - Intra-candle Stop Loss & Take Profit triggers
    - Funding rate cost of carry
    """
    def __init__(
        self,
        initial_balance: float = 10000.0,
        leverage: float = 5.0,
        position_alloc_pct: float = 0.95,
        taker_fee: float = 0.0005,      # 0.05%
        maker_fee: float = 0.0002,      # 0.02%
        slippage: float = 0.0003,       # 0.03%
        funding_rate_8h: float = 0.0001, # 0.01% every 8 hours
        maintenance_margin: float = 0.005 # 0.5% for BTC futures
    ):
        self.initial_balance = initial_balance
        self.leverage = leverage
        self.position_alloc_pct = position_alloc_pct
        self.taker_fee = taker_fee
        self.maker_fee = maker_fee
        self.slippage = slippage
        self.funding_rate_8h = funding_rate_8h
        self.maintenance_margin = maintenance_margin

    def run(self, df: pd.DataFrame, strategy) -> dict:
        """
        Executes backtest against OHLCV data using the provided strategy.
        """
        df_strat = strategy.generate_signals(df.copy())
        
        balance = self.initial_balance
        position = 0          # 1 = Long, -1 = Short, 0 = Flat
        entry_price = 0.0
        pos_margin = 0.0      # Margin locked in trade
        notional_size = 0.0   # pos_margin * leverage
        contracts = 0.0       # notional_size / entry_price
        stop_loss_price = 0.0
        take_profit_price = 0.0
        liq_price = 0.0
        entry_time = None

        trades = []
        equity_curve = []
        liquidations = 0
        total_fees_paid = 0.0
        total_funding_paid = 0.0

        n = len(df_strat)

        for i in range(1, n):
            current_row = df_strat.iloc[i]
            prev_row = df_strat.iloc[i - 1]
            t = current_row['timestamp']
            open_p = current_row['open']
            high_p = current_row['high']
            low_p = current_row['low']
            close_p = current_row['close']

            # 1. Deduct funding rate if holding a position at funding intervals (00:00, 08:00, 16:00 UTC)
            if position != 0:
                hour = t.hour if hasattr(t, 'hour') else pd.to_datetime(t).hour
                minute = t.minute if hasattr(t, 'minute') else pd.to_datetime(t).minute
                if hour in (0, 8, 16) and minute == 0:
                    # Long pays funding if funding rate is positive; short receives it
                    funding_fee = notional_size * self.funding_rate_8h * position
                    balance -= funding_fee
                    total_funding_paid += funding_fee

            # 2. Check Intra-candle exits if in position (Liquidation -> Stop Loss -> Take Profit)
            if position != 0:
                exit_price = None
                exit_reason = None

                if position == 1: # LONG POSITION
                    # Check Liquidation
                    if low_p <= liq_price:
                        exit_price = liq_price
                        exit_reason = "LIQUIDATION"
                        liquidations += 1
                    # Check Stop Loss
                    elif stop_loss_price > 0 and low_p <= stop_loss_price:
                        exit_price = stop_loss_price * (1 - self.slippage)
                        exit_reason = "STOP_LOSS"
                    # Check Take Profit
                    elif take_profit_price > 0 and high_p >= take_profit_price:
                        exit_price = take_profit_price * (1 - self.slippage)
                        exit_reason = "TAKE_PROFIT"

                elif position == -1: # SHORT POSITION
                    # Check Liquidation
                    if high_p >= liq_price:
                        exit_price = liq_price
                        exit_reason = "LIQUIDATION"
                        liquidations += 1
                    # Check Stop Loss
                    elif stop_loss_price > 0 and high_p >= stop_loss_price:
                        exit_price = stop_loss_price * (1 + self.slippage)
                        exit_reason = "STOP_LOSS"
                    # Check Take Profit
                    elif take_profit_price > 0 and low_p <= take_profit_price:
                        exit_price = take_profit_price * (1 + self.slippage)
                        exit_reason = "TAKE_PROFIT"

                # Execute Exit if triggered
                if exit_price is not None:
                    # Calculate PnL
                    price_change_pct = (exit_price - entry_price) / entry_price if position == 1 else (entry_price - exit_price) / entry_price
                    raw_pnl = notional_size * price_change_pct
                    
                    # Exit fee (taker fee on exit notional)
                    exit_notional = contracts * exit_price
                    exit_fee = exit_notional * self.taker_fee
                    total_fees_paid += exit_fee

                    net_pnl = raw_pnl - exit_fee
                    if exit_reason == "LIQUIDATION":
                        # In liquidation, entire margin is lost
                        net_pnl = -pos_margin
                        balance = max(0.0, balance - pos_margin)
                    else:
                        balance += net_pnl

                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': t,
                        'type': 'LONG' if position == 1 else 'SHORT',
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl_pct': price_change_pct * self.leverage * 100,
                        'net_pnl': net_pnl,
                        'exit_reason': exit_reason,
                        'balance_after': balance
                    })

                    position = 0
                    contracts = 0.0
                    notional_size = 0.0
                    pos_margin = 0.0

            # 3. Check for New Signal or Strategy Reversal from previous candle's close
            target_signal = prev_row['signal']

            # If signal changed, close existing position if still open
            if position != 0 and target_signal != position and target_signal != 0:
                exit_price = open_p * (1 - self.slippage if position == 1 else 1 + self.slippage)
                price_change_pct = (exit_price - entry_price) / entry_price if position == 1 else (entry_price - exit_price) / entry_price
                raw_pnl = notional_size * price_change_pct
                exit_fee = (contracts * exit_price) * self.taker_fee
                total_fees_paid += exit_fee
                net_pnl = raw_pnl - exit_fee
                balance += net_pnl

                trades.append({
                    'entry_time': entry_time,
                    'exit_time': t,
                    'type': 'LONG' if position == 1 else 'SHORT',
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl_pct': price_change_pct * self.leverage * 100,
                    'net_pnl': net_pnl,
                    'exit_reason': "SIGNAL_REVERSAL",
                    'balance_after': balance
                })
                position = 0
                contracts = 0.0
                notional_size = 0.0
                pos_margin = 0.0

            # Enter New Position on Open
            if position == 0 and target_signal in (1, -1) and balance > 10.0:
                position = int(target_signal)
                entry_time = t
                entry_price = open_p * (1 + self.slippage if position == 1 else 1 - self.slippage)
                
                # Margin calculation
                pos_margin = balance * self.position_alloc_pct
                notional_size = pos_margin * self.leverage
                contracts = notional_size / entry_price

                # Entry fee
                entry_fee = notional_size * self.taker_fee
                total_fees_paid += entry_fee
                balance -= entry_fee

                # Calculate Liquidation Price
                if position == 1: # Long
                    liq_price = entry_price * (1.0 - (1.0 / self.leverage) + self.maintenance_margin)
                else: # Short
                    liq_price = entry_price * (1.0 + (1.0 / self.leverage) - self.maintenance_margin)

                # Set Stop Loss & Take Profit
                sl_pct = prev_row.get('sl_pct', 0.02)
                tp_pct = prev_row.get('tp_pct', 0.05)

                if position == 1:
                    stop_loss_price = entry_price * (1.0 - sl_pct)
                    take_profit_price = entry_price * (1.0 + tp_pct)
                else:
                    stop_loss_price = entry_price * (1.0 + sl_pct)
                    take_profit_price = entry_price * (1.0 - tp_pct)

            # 4. Record Current Candle Equity
            unrealized_pnl = 0.0
            if position != 0:
                p_diff = (close_p - entry_price) if position == 1 else (entry_price - close_p)
                unrealized_pnl = contracts * p_diff

            current_equity = max(0.0, balance + unrealized_pnl)
            equity_curve.append({
                'timestamp': t,
                'equity': current_equity,
                'close': close_p,
                'position': position
            })

            # If account is blown to zero
            if balance <= 1.0 and position == 0:
                break

        # Convert equity to DataFrame
        eq_df = pd.DataFrame(equity_curve)
        trades_df = pd.DataFrame(trades)

        # Compute Performance Metrics
        metrics = self._calculate_metrics(eq_df, trades_df, df_strat['close'].iloc[0], df_strat['close'].iloc[-1])
        metrics['total_fees_paid'] = total_fees_paid
        metrics['total_funding_paid'] = total_funding_paid
        metrics['liquidations'] = liquidations

        return {
            'strategy_name': strategy.name,
            'leverage': self.leverage,
            'metrics': metrics,
            'equity_curve': eq_df,
            'trades': trades_df
        }

    def _calculate_metrics(self, eq_df: pd.DataFrame, trades_df: pd.DataFrame, btc_start: float, btc_end: float) -> dict:
        if eq_df.empty:
            return {'total_return_pct': -100.0}

        final_equity = eq_df['equity'].iloc[-1]
        total_return_pct = ((final_equity - self.initial_balance) / self.initial_balance) * 100.0
        btc_buy_hold_return = ((btc_end - btc_start) / btc_start) * 100.0

        # Drawdown
        peak = eq_df['equity'].cummax()
        dd = (eq_df['equity'] - peak) / peak
        max_drawdown_pct = abs(dd.min()) * 100.0

        # Returns & Sharpe Ratio
        eq_df['returns'] = eq_df['equity'].pct_change().fillna(0)
        mean_ret = eq_df['returns'].mean()
        std_ret = eq_df['returns'].std()
        
        # Annualized Sharpe (assuming 1-hour candles: 24 * 365 = 8760 periods/yr)
        sharpe_ratio = (mean_ret / std_ret * np.sqrt(8760)) if std_ret > 0 else 0.0

        # Sortino Ratio (downside deviation only)
        downside_returns = eq_df['returns'][eq_df['returns'] < 0]
        downside_std = downside_returns.std()
        sortino_ratio = (mean_ret / downside_std * np.sqrt(8760)) if downside_std > 0 else 0.0

        # Trade stats
        total_trades = len(trades_df)
        if total_trades > 0:
            winners = trades_df[trades_df['net_pnl'] > 0]
            losers = trades_df[trades_df['net_pnl'] < 0]
            win_rate = (len(winners) / total_trades) * 100.0
            gross_profit = winners['net_pnl'].sum() if len(winners) > 0 else 0.0
            gross_loss = abs(losers['net_pnl'].sum()) if len(losers) > 0 else 0.0
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')
            avg_trade_pnl = trades_df['net_pnl'].mean()
        else:
            win_rate = 0.0
            profit_factor = 0.0
            avg_trade_pnl = 0.0

        return {
            'initial_balance': self.initial_balance,
            'final_equity': final_equity,
            'total_return_pct': total_return_pct,
            'btc_buy_hold_pct': btc_buy_hold_return,
            'max_drawdown_pct': max_drawdown_pct,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'total_trades': total_trades,
            'win_rate_pct': win_rate,
            'profit_factor': profit_factor,
            'avg_trade_pnl': avg_trade_pnl
        }

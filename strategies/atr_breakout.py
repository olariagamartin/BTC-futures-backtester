import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy

class ATRBreakoutStrategy(BaseStrategy):
    """
    Channel Breakout Strategy with Average True Range (ATR) dynamic stop-loss.
    - Long: Close breaks above highest high of the last N periods.
    - Short: Close breaks below lowest low of the last N periods.
    - Dynamic Stop Loss: ATR multiple (e.g. 2.0 * ATR).
    """
    def __init__(self, channel_period=24, atr_period=14, atr_multiplier=2.0, tp_pct=0.08):
        super().__init__(
            name=f"ATR_Breakout_{channel_period}",
            channel_period=channel_period,
            atr_period=atr_period,
            atr_multiplier=atr_multiplier,
            tp_pct=tp_pct
        )

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        n = self.params['channel_period']
        atr_p = self.params['atr_period']
        mult = self.params['atr_multiplier']

        # Donchian Channel (exclude current candle to prevent lookahead)
        df['channel_high'] = df['high'].shift(1).rolling(window=n).max()
        df['channel_low'] = df['low'].shift(1).rolling(window=n).min()

        # ATR calculation
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift(1)).abs()
        low_close = (df['low'] - df['close'].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=atr_p).mean()

        # Signals
        df['signal'] = 0
        long_cond = df['close'] > df['channel_high']
        short_cond = df['close'] < df['channel_low']

        df.loc[long_cond, 'signal'] = 1
        df.loc[short_cond, 'signal'] = -1

        # Dynamic stop loss percentage derived from ATR / Close
        df['sl_pct'] = (mult * df['atr'] / df['close']).clip(lower=0.015, upper=0.05)
        df['tp_pct'] = self.params['tp_pct']

        return df

import pandas as pd
from strategies.base_strategy import BaseStrategy

class EMACrossoverStrategy(BaseStrategy):
    """
    Trend-following strategy based on Exponential Moving Average (EMA) crossovers.
    Long when Fast EMA > Slow EMA (and optionally above Trend Filter EMA).
    Short when Fast EMA < Slow EMA (and optionally below Trend Filter EMA).
    """
    def __init__(self, fast_period=12, slow_period=26, trend_filter_period=200, sl_pct=0.025, tp_pct=0.06):
        super().__init__(
            name=f"EMA_{fast_period}_{slow_period}",
            fast_period=fast_period,
            slow_period=slow_period,
            trend_filter_period=trend_filter_period,
            sl_pct=sl_pct,
            tp_pct=tp_pct
        )

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        fast_p = self.params['fast_period']
        slow_p = self.params['slow_period']
        trend_p = self.params['trend_filter_period']

        # Calculate EMAs
        df['ema_fast'] = df['close'].ewm(span=fast_p, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=slow_p, adjust=False).mean()
        df['ema_trend'] = df['close'].ewm(span=trend_p, adjust=False).mean()

        # Initialize signal column: 0 = neutral, 1 = long, -1 = short
        df['signal'] = 0

        # Condition for Long: fast > slow and close > 200 EMA
        long_cond = (df['ema_fast'] > df['ema_slow']*1.004) & (df['close'] > df['ema_trend'])
        # Condition for Short: fast < slow and close < 200 EMA
        short_cond = (df['ema_fast']*1.004 < df['ema_slow']) & (df['close'] < df['ema_trend'])

        df.loc[long_cond, 'signal'] = 1
        df.loc[short_cond, 'signal'] = -1

        # Stop loss and take profit percentages
        df['sl_pct'] = self.params['sl_pct']
        df['tp_pct'] = self.params['tp_pct']

        return df

import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy

class RSIBollingerStrategy(BaseStrategy):
    """
    Mean-reversion strategy combining RSI and Bollinger Bands.
    - Long: Price closes below Lower Band and RSI < rsi_oversold (e.g. 30).
    - Short: Price closes above Upper Band and RSI > rsi_overbought (e.g. 70).
    - Exit: Price reaches Middle Band (SMA 20) or hits SL / TP.
    """
    def __init__(self, bb_period=20, bb_std=2.0, rsi_period=14, rsi_oversold=30, rsi_overbought=70, sl_pct=0.02, tp_pct=0.04):
        super().__init__(
            name="RSI_Bollinger_MeanReversion",
            bb_period=bb_period,
            bb_std=bb_std,
            rsi_period=rsi_period,
            rsi_oversold=rsi_oversold,
            rsi_overbought=rsi_overbought,
            sl_pct=sl_pct,
            tp_pct=tp_pct
        )

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        bb_period = self.params['bb_period']
        bb_std = self.params['bb_std']
        rsi_period = self.params['rsi_period']

        # 1. Bollinger Bands
        df['bb_mid'] = df['close'].rolling(window=bb_period).mean()
        df['bb_sigma'] = df['close'].rolling(window=bb_period).std()
        df['bb_upper'] = df['bb_mid'] + (bb_std * df['bb_sigma'])
        df['bb_lower'] = df['bb_mid'] - (bb_std * df['bb_sigma'])

        # 2. Relative Strength Index (RSI)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / (loss.replace(0, np.nan))
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50)

        # 3. Generate Signals
        df['signal'] = 0
        oversold = self.params['rsi_oversold']
        overbought = self.params['rsi_overbought']

        # Enter Long
        long_entry = (df['close'] <= df['bb_lower']) & (df['rsi'] <= oversold)
        # Enter Short
        short_entry = (df['close'] >= df['bb_upper']) & (df['rsi'] >= overbought)

        # We set entries
        df.loc[long_entry, 'signal'] = 1
        df.loc[short_entry, 'signal'] = -1

        df['sl_pct'] = self.params['sl_pct']
        df['tp_pct'] = self.params['tp_pct']

        return df

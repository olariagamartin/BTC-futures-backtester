from abc import ABC, abstractmethod
import pandas as pd

class BaseStrategy(ABC):
    def __init__(self, name: str, **kwargs):
        self.name = name
        self.params = kwargs

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Takes an OHLCV DataFrame and adds at least:
        - 'signal': 1 (Long), -1 (Short), 0 (Flat/Exit)
        Optional columns:
        - 'stop_loss_pct': float (e.g. 0.02 for 2%)
        - 'take_profit_pct': float (e.g. 0.04 for 4%)
        """
        pass

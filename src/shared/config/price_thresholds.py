import os
from decimal import Decimal
from typing import Any, Dict


class PriceThresholds:
    def __init__(self, config: Dict[str, Any] = None):
        self.low_threshold = Decimal(
            str(config.get("low_threshold") or os.getenv("PRICE_THRESHOLD_LOW", "1.2"))
        )
        self.high_threshold = Decimal(
            str(
                config.get("high_threshold") or os.getenv("PRICE_THRESHOLD_HIGH", "2.0")
            )
        )
        self.stop_loss = Decimal(
            str(config.get("stop_loss") or os.getenv("PRICE_STOP_LOSS", "0.9"))
        )
        self.take_profit = Decimal(
            str(config.get("take_profit") or os.getenv("PRICE_TAKE_PROFIT", "1.5"))
        )
        self.meme_multiplier = Decimal(
            str(
                config.get("meme_multiplier")
                or os.getenv("PRICE_MEME_MULTIPLIER", "1.1")
            )
        )

        self.validate()

    def validate(self):
        if self.low_threshold <= 0:
            raise ValueError("Low threshold must be positive")
        if self.high_threshold <= self.low_threshold:
            raise ValueError("High threshold must be greater than low threshold")
        if self.stop_loss >= 1:
            raise ValueError("Stop loss must be less than 1")
        if self.take_profit <= 1:
            raise ValueError("Take profit must be greater than 1")
        if self.meme_multiplier <= 0:
            raise ValueError("Meme multiplier must be positive")

    def get_thresholds(self, is_meme: bool = False) -> Dict[str, float]:
        multiplier = self.meme_multiplier if is_meme else Decimal("1.0")
        return {
            "low": float(self.low_threshold * multiplier),
            "high": float(self.high_threshold * multiplier),
            "stop_loss": float(self.stop_loss),
            "take_profit": float(self.take_profit * multiplier),
        }

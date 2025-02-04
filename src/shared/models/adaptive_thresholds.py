from typing import Dict, Any, Optional
import numpy as np
from datetime import datetime, timedelta

class AdaptiveThresholds:
    def __init__(self):
        self._thresholds: Dict[str, Dict[str, float]] = {}
        self._volatility_window = 30  # days
        self._position_window = 14  # days
        self._last_update: Dict[str, datetime] = {}
        self._update_interval = timedelta(hours=4)

    def needs_update(self, symbol: str) -> bool:
        if symbol not in self._last_update:
            return True
        return datetime.utcnow() - self._last_update[symbol] > self._update_interval

    def update_thresholds(self, symbol: str, market_data: Dict[str, Any]) -> None:
        prices = np.array(market_data.get("prices", []))
        volumes = np.array(market_data.get("volumes", []))
        
        if len(prices) < 2:
            return
        
        # Calculate volatility using log returns
        log_returns = np.log(prices[1:] / prices[:-1])
        volatility = np.std(log_returns) * np.sqrt(252)  # Annualized
        
        # Calculate volume profile
        avg_volume = np.mean(volumes)
        volume_std = np.std(volumes)
        
        # Calculate price levels
        current_price = prices[-1]
        price_std = np.std(prices)
        
        self._thresholds[symbol] = {
            "volatility": float(volatility * 1.5),  # 50% buffer
            "max_position_size": float(avg_volume * 0.1),  # 10% of avg volume
            "price_deviation": float(price_std * 2),  # 2 standard deviations
            "min_volume": float(max(float(avg_volume - volume_std), float(avg_volume * 0.2))),
            "stop_loss": float(current_price * (1 - volatility)),
            "take_profit": float(current_price * (1 + volatility * 1.5))
        }
        
        self._last_update[symbol] = datetime.utcnow()

    def get_thresholds(self, symbol: str) -> Optional[Dict[str, float]]:
        return self._thresholds.get(symbol)

    def validate_trade(self, symbol: str, trade: Dict[str, Any]) -> Dict[str, Any]:
        thresholds = self.get_thresholds(symbol)
        if not thresholds:
            return {"valid": False, "reason": "No thresholds available"}
            
        price = trade.get("price", 0)
        size = trade.get("size", 0)
        
        validations = {
            "size_valid": size <= thresholds["max_position_size"],
            "price_valid": abs(price - trade.get("market_price", price)) <= thresholds["price_deviation"],
            "stop_loss_valid": trade.get("stop_loss", 0) >= thresholds["stop_loss"],
            "take_profit_valid": trade.get("take_profit", float("inf")) <= thresholds["take_profit"]
        }
        
        return {
            "valid": all(validations.values()),
            "validations": validations,
            "thresholds": thresholds
        }

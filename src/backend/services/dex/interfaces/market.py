"""Market data interface definitions for DEX services."""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional


class IMarketDataService(ABC):
    """Interface for DEX market data operations."""

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict:
        """Get current ticker data for a trading pair.

        Args:
            symbol: Trading pair symbol (e.g. "SOL/USDC")

        Returns:
            Dict containing current price, volume, etc.
        """
        pass

    @abstractmethod
    async def get_orderbook(
        self, symbol: str, depth: int = 100
    ) -> Dict[str, List[List[Decimal]]]:
        """Get current orderbook for a trading pair.

        Args:
            symbol: Trading pair symbol
            depth: Depth of orderbook to return

        Returns:
            Dict containing bids and asks arrays
        """
        pass

    @abstractmethod
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Get recent trades for a trading pair.

        Args:
            symbol: Trading pair symbol
            limit: Number of trades to return

        Returns:
            List of recent trade details
        """
        pass

    @abstractmethod
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[Dict]:
        """Get historical kline/candlestick data.

        Args:
            symbol: Trading pair symbol
            interval: Kline interval (e.g. "1m", "5m", "1h")
            start_time: Start time for history query
            end_time: End time for history query
            limit: Maximum number of klines to return

        Returns:
            List of kline data
        """
        pass

    @abstractmethod
    async def get_24h_stats(self, symbol: str) -> Dict:
        """Get 24-hour statistics for a trading pair.

        Args:
            symbol: Trading pair symbol

        Returns:
            Dict containing 24h volume, price change, etc.
        """
        pass

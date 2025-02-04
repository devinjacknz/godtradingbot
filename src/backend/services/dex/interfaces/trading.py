"""Trading interface definitions for DEX services."""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional


class ITradingService(ABC):
    """Interface for DEX trading operations."""

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: Decimal,
        price: Optional[Decimal] = None,
        **kwargs,
    ) -> Dict[str, str]:
        """Place a new order on the DEX.

        Args:
            symbol: Trading pair symbol (e.g. "SOL/USDC")
            side: Order side ("buy" or "sell")
            order_type: Order type ("limit" or "market")
            amount: Order amount in base currency
            price: Limit price (required for limit orders)
            **kwargs: Additional parameters specific to DEX

        Returns:
            Dict containing order details including order_id
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order.

        Args:
            order_id: Unique identifier of the order

        Returns:
            True if order was cancelled successfully
        """
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> Dict:
        """Get current status of an order.

        Args:
            order_id: Unique identifier of the order

        Returns:
            Dict containing order status and details
        """
        pass

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get list of open orders.

        Args:
            symbol: Optional trading pair to filter by

        Returns:
            List of open order details
        """
        pass

    @abstractmethod
    async def get_order_history(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Get historical orders.

        Args:
            symbol: Optional trading pair to filter by
            start_time: Start time for history query
            end_time: End time for history query
            limit: Maximum number of orders to return

        Returns:
            List of historical order details
        """
        pass

"""Liquidity pool interface definitions for DEX services."""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple


class ILiquidityPoolService(ABC):
    """Interface for DEX liquidity pool operations."""

    @abstractmethod
    async def get_pool_info(self, pool_id: str) -> Dict:
        """Get information about a specific liquidity pool.

        Args:
            pool_id: Unique identifier of the pool

        Returns:
            Dict containing pool details (tokens, reserves, etc.)
        """
        pass

    @abstractmethod
    async def add_liquidity(
        self,
        pool_id: str,
        amounts: List[Decimal],
        min_shares: Optional[Decimal] = None,
        **kwargs,
    ) -> Dict:
        """Add liquidity to a pool.

        Args:
            pool_id: Pool identifier
            amounts: List of token amounts to add
            min_shares: Minimum LP tokens to receive
            **kwargs: Additional parameters

        Returns:
            Dict containing transaction details
        """
        pass

    @abstractmethod
    async def remove_liquidity(
        self,
        pool_id: str,
        shares: Decimal,
        min_amounts: Optional[List[Decimal]] = None,
        **kwargs,
    ) -> Dict:
        """Remove liquidity from a pool.

        Args:
            pool_id: Pool identifier
            shares: Amount of LP tokens to burn
            min_amounts: Minimum tokens to receive
            **kwargs: Additional parameters

        Returns:
            Dict containing transaction details
        """
        pass

    @abstractmethod
    async def get_pool_stats(
        self,
        pool_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict:
        """Get pool statistics over time period.

        Args:
            pool_id: Pool identifier
            start_time: Start of time period
            end_time: End of time period

        Returns:
            Dict containing pool statistics
        """
        pass

    @abstractmethod
    async def get_user_positions(
        self, wallet_address: str, pool_id: Optional[str] = None
    ) -> List[Dict]:
        """Get user's liquidity positions.

        Args:
            wallet_address: User's wallet address
            pool_id: Optional pool to filter by

        Returns:
            List of liquidity positions
        """
        pass

    @abstractmethod
    async def calculate_swap(
        self, pool_id: str, token_in: str, token_out: str, amount_in: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """Calculate expected swap output and price impact.

        Args:
            pool_id: Pool identifier
            token_in: Input token symbol
            token_out: Output token symbol
            amount_in: Input amount

        Returns:
            Tuple of (expected_output, price_impact)
        """
        pass

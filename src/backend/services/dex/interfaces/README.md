# DEX Interfaces

This directory contains interface definitions for DEX (Decentralized Exchange) services.

## Directory Structure

- `trading.py` - Trading interface definitions
- `market.py` - Market data interface definitions
- `liquidity.py` - Liquidity pool interface definitions
- `types.py` - Common type definitions

## Interface Guidelines

1. All interfaces should be defined using abstract base classes
2. Use type hints for all method parameters and return values
3. Include comprehensive docstrings for all interfaces
4. Follow SOLID principles, especially Interface Segregation

## Example Usage

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

class ITradingService(ABC):
    @abstractmethod
    async def place_order(self, order: Dict) -> str:
        """Place a new order on the DEX"""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order"""
        pass
``` 
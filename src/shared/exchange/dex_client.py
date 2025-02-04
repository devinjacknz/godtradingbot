import json
from datetime import datetime
from typing import Any, Dict, Optional

import aiohttp


class DEXClient:
    """Client for interacting with multiple DEX APIs."""

    def __init__(self):
        self.session = None
        self.base_urls = {
            "uniswap": "https://api.uniswap.org/v1",
            "jupiter": "https://quote-api.jup.ag/v6",
            "raydium": "https://api.raydium.io/v2",
            "pancakeswap": "https://api.pancakeswap.info/api/v2",
            "liquidswap": "https://api.liquidswap.com",
            "hyperliquid": "https://api.hyperliquid.xyz",
        }
        self.jupiter_client = None

    async def start(self):
        """Initialize HTTP session."""
        self.session = aiohttp.ClientSession()

    async def stop(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
        if self.jupiter_client:
            await self.jupiter_client.stop()
            self.jupiter_client = None

    async def get_quote(
        self, dex: str, token_in: str, token_out: str, amount: float
    ) -> Dict[str, Any]:
        """Get quote from specified DEX."""
        if dex == "jupiter":
            if not self.jupiter_client:
                from .jupiter_client import JupiterClient

                self.jupiter_client = JupiterClient({"slippage_bps": 100})
                await self.jupiter_client.start()
            return await self.jupiter_client.get_quote(
                token_in, token_out, int(amount * 1e9)
            )

        if not self.session:
            await self.start()
            if not self.session:
                return {"error": "Failed to initialize session"}

        endpoints = {
            "uniswap": "/quote",
            "jupiter": "/quote",
            "raydium": "/quote",
            "pancakeswap": "/pairs",
            "liquidswap": "/quote",
            "hyperliquid": "/quote",
        }

        params = {"tokenIn": token_in, "tokenOut": token_out, "amount": str(amount)}

        try:
            async with self.session.get(
                f"{self.base_urls[dex]}{endpoints[dex]}", params=params
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {
                        "error": f"Failed to get quote from {dex}",
                        "status": response.status,
                        "message": await response.text(),
                    }
        except Exception as e:
            return {"error": str(e)}

    async def get_liquidity(self, dex: str, token: str) -> Dict[str, Any]:
        """Get liquidity information for a token."""
        if not self.session:
            await self.start()
            if not self.session:
                return {"error": "Failed to initialize session"}

        endpoints = {
            "uniswap": "/pools",
            "jupiter": "/market-depth",
            "raydium": "/pools",
            "pancakeswap": "/tokens",
            "liquidswap": "/pools",
            "hyperliquid": "/pools",
        }

        try:
            async with self.session.get(
                f"{self.base_urls[dex]}{endpoints[dex]}", params={"token": token}
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {
                        "error": f"Failed to get liquidity from {dex}",
                        "status": response.status,
                        "message": await response.text(),
                    }
        except Exception as e:
            return {"error": str(e)}

    async def get_market_data(self, dex: str) -> Dict[str, Any]:
        """Get market data from DEX."""
        if not self.session:
            await self.start()
            if not self.session:
                return {"error": "Failed to initialize session"}

        endpoints = {
            "uniswap": "/pairs",
            "jupiter": "/market",
            "raydium": "/market",
            "pancakeswap": "/summary",
            "liquidswap": "/market",
            "hyperliquid": "/market",
        }

        try:
            async with self.session.get(
                f"{self.base_urls[dex]}{endpoints[dex]}"
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {
                        "error": f"Failed to get market data from {dex}",
                        "status": response.status,
                        "message": await response.text(),
                    }
        except Exception as e:
            return {"error": str(e)}

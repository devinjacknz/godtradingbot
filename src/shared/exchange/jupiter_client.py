import json
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


class JupiterClient:
    def __init__(self, config: Dict[str, Any]):
        self.base_url = "https://quote-api.jup.ag/v6"
        self.slippage_bps = config.get("slippage_bps", 100)
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def stop(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: Optional[int] = None,
    ) -> Dict[str, Any]:
        await self.start()
        assert self.session is not None

        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": str(slippage_bps or self.slippage_bps),
        }

        try:
            async with self.session.get(
                f"{self.base_url}/quote", params=params
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Jupiter API error: {error_text}")
                    return {"error": f"Jupiter API error: {response.status}"}

                return await response.json()

        except Exception as e:
            logger.error(f"Error getting Jupiter quote: {str(e)}")
            return {"error": f"Failed to get quote: {str(e)}"}

    async def get_swap_instruction(
        self, quote_response: Dict[str, Any]
    ) -> Dict[str, Any]:
        await self.start()
        assert self.session is not None

        try:
            async with self.session.post(
                f"{self.base_url}/swap", json=quote_response
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Jupiter swap instruction error: {error_text}")
                    return {
                        "error": f"Jupiter swap instruction error: {response.status}"
                    }

                return await response.json()

        except Exception as e:
            logger.error(f"Error getting swap instruction: {str(e)}")
            return {"error": f"Failed to get swap instruction: {str(e)}"}

    async def get_price(
        self, input_mint: str, output_mint: str, amount: int
    ) -> Optional[Decimal]:
        quote = await self.get_quote(input_mint, output_mint, amount)
        if "error" in quote:
            return None

        try:
            out_amount = Decimal(quote.get("outAmount", "0"))
            in_amount = Decimal(str(amount))
            if in_amount == 0:
                return None
            return out_amount / in_amount
        except Exception as e:
            logger.error(f"Error calculating price: {str(e)}")
            return None

    async def get_routes(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: Optional[int] = None,
    ) -> Dict[str, Any]:
        await self.start()
        assert self.session is not None

        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": str(slippage_bps or self.slippage_bps),
        }

        try:
            async with self.session.get(
                f"{self.base_url}/routes", params=params
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Jupiter routes error: {error_text}")
                    return {"error": f"Jupiter routes error: {response.status}"}

                return await response.json()

        except Exception as e:
            logger.error(f"Error getting routes: {str(e)}")
            return {"error": f"Failed to get routes: {str(e)}"}

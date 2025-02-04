from decimal import Decimal
import httpx
import logging
from typing import Dict, Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class JupiterAPI:
    def __init__(self):
        self.base_url = "https://quote-api.jup.ag/v6"
        self.client = httpx.AsyncClient(timeout=10.0)
        
    async def get_quote(
        self,
        input_token: str,
        output_token: str,
        amount: Decimal,
        slippage_bps: int = 100
    ) -> Optional[Dict]:
        try:
            response = await self.client.get(
                f"{self.base_url}/quote",
                params={
                    "inputMint": input_token,
                    "outputMint": output_token,
                    "amount": str(int(amount * Decimal("1e9"))),
                    "slippageBps": slippage_bps
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "input_token": input_token,
                "output_token": output_token,
                "input_amount": amount,
                "output_amount": Decimal(str(data["outAmount"])) / Decimal("1e9"),
                "price_impact": Decimal(str(data.get("priceImpactPct", "0"))) / 100,
                "route": data["routePlan"]
            }
            
        except Exception as e:
            logger.error(f"Failed to get Jupiter quote: {str(e)}")
            return None
    
    async def get_swap_instruction(self, quote: Dict) -> Optional[Dict]:
        try:
            response = await self.client.post(
                f"{self.base_url}/swap",
                json={
                    "quoteResponse": quote["original_response"],
                    "userPublicKey": quote["user_pubkey"],
                    "wrapUnwrapSOL": True
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "swap_transaction": data["swapTransaction"],
                "signatures": data.get("signatures", [])
            }
            
        except Exception as e:
            logger.error(f"Failed to get swap instruction: {str(e)}")
            return None
            
    async def get_token_list(self) -> Optional[Dict]:
        try:
            response = await self.client.get(
                "https://token.jup.ag/all"
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to get token list: {str(e)}")
            return None
            
    async def get_price(self, token_mint: str) -> Optional[Decimal]:
        try:
            response = await self.client.get(
                f"https://price.jup.ag/v4/price",
                params={
                    "ids": token_mint
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if token_mint in data["data"]:
                return Decimal(str(data["data"][token_mint]["price"]))
            return None
            
        except Exception as e:
            logger.error(f"Failed to get price: {str(e)}")
            return None

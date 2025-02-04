from decimal import Decimal
import httpx
import logging
from typing import Dict, Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class RaydiumAPI:
    def __init__(self):
        self.base_url = "https://api.raydium.io/v2"
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
                f"{self.base_url}/main/quote",
                params={
                    "inputMint": input_token,
                    "outputMint": output_token,
                    "amount": str(int(amount * Decimal("1e9"))),
                    "slippage": slippage_bps
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "input_token": input_token,
                "output_token": output_token,
                "input_amount": amount,
                "output_amount": Decimal(str(data["outAmount"])) / Decimal("1e9"),
                "price_impact": Decimal(str(data.get("priceImpact", "0"))) / 100,
                "route": data.get("route", [])
            }
            
        except Exception as e:
            logger.error(f"Failed to get Raydium quote: {str(e)}")
            return None
    
    async def get_pool_info(
        self,
        token_in: str,
        token_out: str
    ) -> Optional[Dict]:
        try:
            response = await self.client.get(
                f"{self.base_url}/pools",
                params={
                    "tokenMintA": token_in,
                    "tokenMintB": token_out
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if not data["pools"]:
                return None
                
            pool = data["pools"][0]
            return {
                "liquidity_usd": Decimal(str(pool["liquidity"])),
                "volume_24h": Decimal(str(pool["volume24h"])),
                "price": Decimal(str(pool["price"])),
                "spread": Decimal(str(pool.get("spread", "0.001")))
            }
            
        except Exception as e:
            logger.error(f"Failed to get pool info: {str(e)}")
            return None
            
    async def get_token_list(self) -> Optional[Dict]:
        try:
            response = await self.client.get(
                f"{self.base_url}/tokens"
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Failed to get token list: {str(e)}")
            return None

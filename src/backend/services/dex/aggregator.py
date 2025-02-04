from decimal import Decimal
import logging
from typing import Dict, List, Optional
from fastapi import HTTPException
from solana.rpc.async_api import AsyncClient
from src.shared.models.trading import TradeSignal
from src.backend.monitoring.metrics import TradingMetrics

logger = logging.getLogger(__name__)

class DEXAggregator:
    def __init__(self):
        self._metrics = TradingMetrics()
        self._rpc_client = AsyncClient("https://api.mainnet-beta.solana.com")
        self._min_liquidity = Decimal("100000")
        self._max_slippage = Decimal("0.02")
        self._min_volume = Decimal("50000")
        self._max_spread = Decimal("0.01")
        
        self.supported_dexes = {
            "jupiter": {
                "enabled": True,
                "priority": 1,
                "base_url": "https://quote-api.jup.ag/v6"
            },
            "raydium": {
                "enabled": True,
                "priority": 2,
                "base_url": "https://api.raydium.io/v2"
            },
            "orca": {
                "enabled": True,
                "priority": 3,
                "base_url": "https://api.orca.so"
            }
        }
    
    async def get_best_quote(self, input_token: str, output_token: str, amount: Decimal) -> Dict:
        quotes = []
        for dex_name, dex_config in self.supported_dexes.items():
            if not dex_config["enabled"]:
                continue
                
            try:
                quote = await self._get_dex_quote(
                    dex_name,
                    dex_config,
                    input_token,
                    output_token,
                    amount
                )
                if quote:
                    quotes.append(quote)
            except Exception as e:
                logger.error(f"Failed to get quote from {dex_name}: {str(e)}")
        
        if not quotes:
            raise HTTPException(400, "No valid quotes found")
            
        return min(quotes, key=lambda x: x["price_impact"])
    
    async def execute_swap(self, quote: Dict) -> Dict:
        try:
            dex_name = quote["dex"]
            dex_config = self.supported_dexes[dex_name]
            
            result = await self._execute_dex_swap(dex_name, dex_config, quote)
            
            self._metrics.swap_volume.inc(float(quote["input_amount"]))
            self._metrics.swap_count.inc()
            
            return {
                "status": "completed",
                "input_amount": quote["input_amount"],
                "output_amount": result["output_amount"],
                "price_impact": result["price_impact"],
                "transaction_hash": result["tx_hash"],
                "dex_used": dex_name
            }
            
        except Exception as e:
            logger.error(f"Swap execution failed: {str(e)}")
            raise HTTPException(500, f"Swap execution failed: {str(e)}")
    
    async def get_pool_info(self, token_pair: str) -> Dict:
        tokens = token_pair.split("/")
        if len(tokens) != 2:
            raise HTTPException(400, "Invalid token pair format")
            
        pool_data = {}
        for dex_name, dex_config in self.supported_dexes.items():
            if not dex_config["enabled"]:
                continue
                
            try:
                data = await self._get_dex_pool_info(
                    dex_name,
                    dex_config,
                    tokens[0],
                    tokens[1]
                )
                if data:
                    pool_data[dex_name] = data
            except Exception as e:
                logger.error(f"Failed to get pool info from {dex_name}: {str(e)}")
        
        if not pool_data:
            raise HTTPException(404, "No pool information found")
            
        return {
            "token_pair": token_pair,
            "dex_data": pool_data,
            "best_liquidity": max(
                pool_data.values(),
                key=lambda x: x["liquidity_usd"]
            )
        }
    
    async def _get_dex_quote(
        self,
        dex_name: str,
        dex_config: Dict,
        input_token: str,
        output_token: str,
        amount: Decimal
    ) -> Optional[Dict]:
        if dex_name == "jupiter":
            from .jupiter import JupiterAPI
            jupiter = JupiterAPI()
            quote = await jupiter.get_quote(
                input_token,
                output_token,
                amount
            )
            if quote:
                quote["dex"] = dex_name
                return quote
        elif dex_name == "raydium":
            from .raydium import RaydiumAPI
            raydium = RaydiumAPI()
            quote = await raydium.get_quote(
                input_token,
                output_token,
                amount
            )
            if quote:
                quote["dex"] = dex_name
                return quote
        elif dex_name == "orca":
            from .orca import OrcaAPI
            orca = OrcaAPI()
            quote = await orca.get_quote(
                input_token,
                output_token,
                amount
            )
            if quote:
                quote["dex"] = dex_name
                return quote
        else:
            logger.warning(f"Quote retrieval not implemented for {dex_name}")
            
        return None
    
    async def _execute_dex_swap(
        self,
        dex_name: str,
        dex_config: Dict,
        quote: Dict
    ) -> Dict:
        if dex_name == "jupiter":
            from .jupiter import JupiterAPI
            jupiter = JupiterAPI()
            swap = await jupiter.get_swap_instruction(quote)
            if not swap:
                raise HTTPException(500, "Failed to get swap instruction")
                
            return {
                "output_amount": quote["output_amount"],
                "price_impact": quote["price_impact"],
                "tx_hash": swap["signatures"][0] if swap["signatures"] else None,
                "swap_transaction": swap["swap_transaction"]
            }
        else:
            raise HTTPException(400, f"Swap execution not implemented for {dex_name}")
    
    async def _get_dex_pool_info(
        self,
        dex_name: str,
        dex_config: Dict,
        token_in: str,
        token_out: str
    ) -> Optional[Dict]:
        if dex_name == "jupiter":
            from .jupiter import JupiterAPI
            jupiter = JupiterAPI()
            price = await jupiter.get_price(token_in)
            if price:
                return {
                    "liquidity_usd": price * Decimal("1000000"),
                    "volume_24h": price * Decimal("500000"),
                    "price": price,
                    "spread": Decimal("0.001")
                }
        elif dex_name == "raydium":
            from .raydium import RaydiumAPI
            raydium = RaydiumAPI()
            pool_info = await raydium.get_pool_info(token_in, token_out)
            if pool_info:
                return pool_info
        elif dex_name == "orca":
            from .orca import OrcaAPI
            orca = OrcaAPI()
            pool_info = await orca.get_pool_info(token_in, token_out)
            if pool_info:
                return pool_info
        
        return None

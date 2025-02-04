import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

from src.shared.models.market_data import MarketData


class MemeTokenScanner:
    def __init__(self, config: Dict[str, Any]):
        self.max_market_cap = config.get("max_market_cap", 30000)
        self.min_volume = config.get("min_volume", 1000)
        self.coingecko_api_url = "https://api.coingecko.com/api/v3"
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes

    async def scan_for_meme_tokens(self) -> List[Dict[str, Any]]:
        try:
            async with aiohttp.ClientSession() as session:
                # Get Solana tokens from CoinGecko
                async with session.get(
                    f"{self.coingecko_api_url}/coins/list",
                    params={"include_platform": "true"},
                ) as response:
                    if response.status != 200:
                        logging.error(f"CoinGecko API error: {response.status}")
                        return []

                    tokens = await response.json()
                    solana_tokens = [
                        token
                        for token in tokens
                        if token.get("platforms", {}).get("solana")
                    ]

                    # Get market data for Solana tokens
                    low_cap_tokens = []
                    for token in solana_tokens:
                        token_id = token["id"]

                        # Check cache
                        cache_key = f"market_data:{token_id}"
                        if cache_key in self.cache:
                            cached_data = self.cache[cache_key]
                            if (
                                datetime.now() - cached_data["timestamp"]
                            ).total_seconds() < self.cache_ttl:
                                if cached_data["market_cap"] <= self.max_market_cap:
                                    low_cap_tokens.append(cached_data)
                                continue

                        # Fetch market data
                        async with session.get(
                            f"{self.coingecko_api_url}/simple/price",
                            params={
                                "ids": token_id,
                                "vs_currencies": "usd",
                                "include_market_cap": "true",
                                "include_24hr_vol": "true",
                            },
                        ) as market_response:
                            if market_response.status != 200:
                                continue

                            market_data = await market_response.json()
                            if token_id not in market_data:
                                continue

                            token_market_data = market_data[token_id]
                            market_cap = token_market_data.get("usd_market_cap", 0)
                            volume = token_market_data.get("usd_24h_vol", 0)

                            token_data = {
                                "id": token_id,
                                "symbol": token["symbol"].upper(),
                                "name": token["name"],
                                "price": token_market_data.get("usd", 0),
                                "market_cap": market_cap,
                                "volume": volume,
                                "address": token["platforms"]["solana"],
                                "timestamp": datetime.now(),
                            }

                            # Cache the data
                            self.cache[cache_key] = token_data

                            if (
                                market_cap <= self.max_market_cap
                                and volume >= self.min_volume
                            ):
                                low_cap_tokens.append(token_data)

                    return low_cap_tokens

        except Exception as e:
            logging.error(f"Error scanning for meme tokens: {str(e)}")
            return []

    async def get_token_market_data(self, token_id: str) -> Optional[MarketData]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.coingecko_api_url}/simple/price",
                    params={
                        "ids": token_id,
                        "vs_currencies": "usd",
                        "include_market_cap": "true",
                        "include_24hr_vol": "true",
                    },
                ) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    if token_id not in data:
                        return None

                    token_data = data[token_id]
                    return MarketData(
                        symbol=token_id,
                        exchange="coingecko",
                        timestamp=datetime.now(),
                        price=token_data.get("usd", 0),
                        volume=token_data.get("usd_24h_vol", 0),
                        timeframe="1h",
                        prices=[token_data.get("usd", 0)],
                        volumes=[token_data.get("usd_24h_vol", 0)],
                    )

        except Exception as e:
            logging.error(f"Error fetching token market data: {str(e)}")
            return None

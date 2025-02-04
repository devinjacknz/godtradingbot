import logging
from typing import Any, Dict

import aiohttp

from src.shared.models.errors import TradingError

logger = logging.getLogger(__name__)


async def execute_trade_in_go(trade_params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        url = "http://localhost:9000/execute"
        logger.info(f"Executing trade via Go service: {trade_params['id']}")

        if "amount" not in trade_params.get("params", {}):
            raise TradingError("Trade amount is required")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=trade_params, timeout=10) as response:
                response.raise_for_status()
                result = await response.json()

                if result.get("status") == "failed":
                    raise TradingError(
                        result.get("error", "Unknown error from Go service")
                    )

                logger.info(f"Trade executed successfully: {result['id']}")
                return result

    except aiohttp.ClientError as e:
        logger.error(f"Failed to execute trade {trade_params.get('id')}: {str(e)}")
        raise TradingError(f"Failed to execute trade in Go service: {str(e)}")

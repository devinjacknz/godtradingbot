import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

import grpc.aio
from google.protobuf.json_format import MessageToDict

from src.shared.logging_config import setup_logging

from .pb import trading_pb2 as pb
from .pb import trading_pb2_grpc as pb_grpc

setup_logging()
logger = logging.getLogger(__name__)


class TradingExecutorClient:
    def __init__(self, address: str = "localhost:50051"):
        self.channel = grpc.aio.insecure_channel(address)
        self.stub = pb_grpc.TradingExecutorStub(self.channel)
        self.logger = logging.getLogger(__name__)

    async def execute_trade(self, trade_params: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        self.logger.info(
            "Trade request: symbol=%s side=%s amount=%.2f price=%.2f type=%s",
            trade_params["symbol"],
            trade_params["side"],
            float(trade_params["amount"]),
            float(trade_params.get("price", 0)),
            trade_params.get("order_type", "MARKET"),
        )

        try:
            request = pb.TradeRequest(
                symbol=trade_params["symbol"],
                side=trade_params["side"],
                amount=float(trade_params["amount"]),
                price=float(trade_params.get("price", 0)),
                order_type=trade_params.get("order_type", "MARKET"),
                params=trade_params.get("params", {}),
            )

            response = await self.stub.ExecuteTrade(request)
            result = MessageToDict(response)
            self.logger.info(
                "Trade executed: order_id=%s status=%s price=%.2f amount=%.2f",
                result.get("orderId"),
                result.get("status"),
                float(result.get("executedPrice", 0)),
                float(result.get("executedAmount", 0)),
            )
            duration = time.time() - start_time
            self.logger.info(
                "Trade execution completed in %.3fs: order_id=%s",
                duration,
                result.get("orderId"),
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(
                "Trade execution failed after %.3fs: %s",
                duration,
                str(e),
                exc_info=True,
            )
            raise

    async def get_market_data(
        self, symbol: str, data_type: str = "FULL", depth: int = 10
    ) -> AsyncGenerator[Dict[str, Any], None]:
        self.logger.info(
            "Market data request: symbol=%s type=%s depth=%d", symbol, data_type, depth
        )

        request = pb.MarketDataRequest(symbol=symbol, data_type=data_type, depth=depth)

        try:
            async for data in self.stub.GetMarketData(request):
                result = MessageToDict(data)
                self.logger.debug(
                    "Market data received: symbol=%s candles=%d",
                    symbol,
                    len(result.get("candles", [])),
                )
                yield result
        except Exception as e:
            self.logger.error("Market data request failed: %s", str(e), exc_info=True)
            raise

    async def monitor_order_status(
        self, order_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        self.logger.info("Starting order status monitoring: order_id=%s", order_id)
        request = pb.OrderStatusRequest(order_id=order_id)

        try:
            async for status in self.stub.MonitorOrderStatus(request):
                result = MessageToDict(status)
                self.logger.debug(
                    "Order status update: order_id=%s status=%s filled=%.2f remaining=%.2f",
                    order_id,
                    result.get("status"),
                    float(result.get("filledAmount", 0)),
                    float(result.get("remainingAmount", 0)),
                )
                yield result
        except Exception as e:
            self.logger.error(
                "Order status monitoring failed: %s", str(e), exc_info=True
            )
            raise

    async def batch_execute_trades(
        self, trades: list[Dict[str, Any]], atomic: bool = False
    ) -> Dict[str, Any]:
        logger.info("Batch executing %d trades (atomic=%s)", len(trades), atomic)
        try:
            trade_requests = [
                pb.TradeRequest(
                    symbol=t["symbol"],
                    side=t["side"],
                    amount=float(t["amount"]),
                    price=float(t.get("price", 0)),
                    order_type=t.get("order_type", "MARKET"),
                    params=t.get("params", {}),
                )
                for t in trades
            ]

            request = pb.BatchTradeRequest(trades=trade_requests, atomic=atomic)

            response = await self.stub.BatchExecuteTrades(request)
            result = MessageToDict(response)
            logger.info("Batch execution completed: %s", result)
            return result
        except Exception as e:
            logger.error("Failed to execute batch trades: %s", str(e), exc_info=True)
            raise

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        self.logger.info("Getting order status: order_id=%s", order_id)
        try:
            request = pb.OrderStatusRequest(order_id=order_id)
            async for status in self.stub.MonitorOrderStatus(request):
                result = MessageToDict(status)
                self.logger.debug(
                    "Order status received: order_id=%s status=%s",
                    order_id,
                    result.get("status"),
                )
                return result
            return {"status": "not_found", "order_id": order_id}
        except Exception as e:
            self.logger.error("Failed to get order status: %s", str(e), exc_info=True)
            raise

    async def close(self):
        await self.channel.close()


class ExecutorPool:
    def __init__(self, addresses: list[str], pool_size: int = 3):
        self.addresses = addresses
        self.pool_size = pool_size
        self.clients: list[TradingExecutorClient] = []
        self.current = 0
        self._lock = asyncio.Lock()

    async def initialize(self):
        self.clients = [
            TradingExecutorClient(addr) for addr in self.addresses[: self.pool_size]
        ]

    async def get_client(self) -> TradingExecutorClient:
        async with self._lock:
            client = self.clients[self.current]
            self.current = (self.current + 1) % len(self.clients)
            return client

    async def close(self):
        await asyncio.gather(*(client.close() for client in self.clients))

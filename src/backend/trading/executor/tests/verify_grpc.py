import os
import sys

# Add project root to Python path
project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../../")
)
sys.path.insert(0, project_root)

import logging

from src.backend.trading.executor.pb import trading_pb2, trading_pb2_grpc

logger = logging.getLogger(__name__)


def verify_grpc_methods():
    print("\nVerifying gRPC service definitions:")

    # Check service class exists
    if not hasattr(trading_pb2_grpc, "TradingExecutorServicer"):
        print("ERROR: TradingExecutorServicer not found")
        return False

    # Check message types
    required_messages = [
        "TradeRequest",
        "TradeResponse",
        "MarketDataRequest",
        "MarketDataResponse",
        "OrderStatusRequest",
        "OrderStatusResponse",
        "BatchTradeRequest",
        "BatchTradeResponse",
    ]

    for msg in required_messages:
        if not hasattr(trading_pb2, msg):
            print(f"ERROR: Missing message type {msg}")
            return False
        print(f"✓ Found message type {msg}")

    # Check required methods
    required_methods = [
        "ExecuteTrade",
        "GetMarketData",
        "MonitorOrderStatus",
        "BatchExecuteTrades",
    ]

    servicer = trading_pb2_grpc.TradingExecutorServicer
    for method in required_methods:
        if not hasattr(servicer, method):
            print(f"ERROR: Missing method {method}")
            return False
        print(f"✓ Found method {method}")

    print("\nAll required gRPC components verified successfully")


if __name__ == "__main__":
    verify_grpc_methods()

import asyncio

import pytest

from .grpc_client import TradeServiceClient


def test_market_data():
    client = TradeServiceClient()
    data = client.get_market_data("SOL/USDC", "1m", 100)
    assert len(data) > 0
    assert all(
        k in data[0] for k in ["open", "high", "low", "close", "volume", "timestamp"]
    )


def test_trade_execution():
    client = TradeServiceClient()
    trade = client.execute_trade(
        symbol="SOL/USDC", side="buy", amount=1.0, price=100.0, order_type="market"
    )
    assert trade["order_id"]
    assert trade["status"] in ["pending", "executed"]

    status = client.get_order_status(trade["order_id"])
    assert status["order_id"] == trade["order_id"]
    assert status["status"] in ["pending", "executed", "not_found"]


def test_price_updates():
    updates = []

    def callback(update):
        updates.append(update)
        if len(updates) >= 2:
            raise KeyboardInterrupt()

    client = TradeServiceClient()
    try:
        client.subscribe_price_updates(["SOL/USDC"], callback, update_interval_ms=100)
    except KeyboardInterrupt:
        pass

    assert len(updates) >= 2
    assert all(
        k in updates[0]
        for k in ["symbol", "price", "volume", "timestamp", "bid", "ask"]
    )

from typing import Any, Dict, List, Optional

"""Trade executor module for handling trade execution and management."""
import logging
from datetime import datetime

from src.shared.logging_config import setup_logging
from src.shared.models.errors import TradingError

from ...trading_agent.agents.wallet_manager import WalletManager
from .base_executor import BaseExecutor
from .grpc_client import ExecutorPool, TradingExecutorClient

setup_logging()


class TradeExecutor(BaseExecutor):
    """Handles trade execution, monitoring, and management using gRPC services."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.wallet_manager = WalletManager()
        self.active_trades: Dict[str, Dict[str, Any]] = {}
        self.trade_history: List[Dict[str, Any]] = []
        self.grpc_client = TradingExecutorClient()
        self.executor_pool = ExecutorPool(["localhost:50051"])
        self.logger = logging.getLogger(__name__)

    async def validate_with_ai(self, trade_params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate trade parameters using DeepSeek R1 model."""
        from src.shared.ai_analyzer import AIAnalyzer

        analyzer = AIAnalyzer()
        if not await analyzer.start():
            raise TradingError("Failed to initialize AI analyzer")
        try:
            validation = await analyzer.validate_trade(trade_params)

            # Check validation result
            if not validation.get("is_valid", False):
                raise TradingError(
                    f"AI validation failed: {validation.get('reason', 'Unknown reason')}"
                )

            # Verify risk metrics are within acceptable bounds
            risk = validation.get("risk_assessment", {})
            if risk.get("risk_level", 1.0) > 0.8:
                raise TradingError(f"Risk level too high: {risk.get('risk_level')}")
            if risk.get("max_loss", 100.0) > trade_params.get(
                "max_loss_threshold", 10.0
            ):
                raise TradingError(
                    f"Maximum potential loss exceeds threshold: {risk.get('max_loss')}%"
                )

            # Verify market conditions alignment
            metrics = validation.get("validation_metrics", {})
            if metrics.get("market_conditions_alignment", 0.0) < 0.6:
                raise TradingError(
                    f"Poor market conditions alignment: {metrics.get('market_conditions_alignment')}"
                )
            if metrics.get("risk_reward_ratio", 0.0) < 1.5:
                raise TradingError(
                    f"Insufficient risk-reward ratio: {metrics.get('risk_reward_ratio')}"
                )

            return validation
        finally:
            if not await analyzer.stop():
                self.logger.warning("Failed to cleanly stop AI analyzer")

    async def execute_trade(self, trade_params: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.info(
            "Trade request received: symbol=%s side=%s amount=%.2f price=%.2f type=%s",
            trade_params.get("symbol"),
            trade_params.get("side"),
            float(trade_params.get("amount", 0)),
            float(trade_params.get("price", 0)),
            trade_params.get("order_type", "market"),
        )

        if not self.wallet_manager.is_initialized():
            self.logger.error("Trade rejected: wallet not initialized")
            raise TradingError("Wallet not initialized")

        balance = await self.wallet_manager.get_balance()
        if balance < 0.5:
            self.logger.error(
                "Trade rejected: insufficient balance (%.2f SOL)", balance
            )
            raise TradingError("Insufficient balance (minimum 0.5 SOL required)")

        # Validate trade with AI before execution
        try:
            self.logger.info("Starting AI validation for trade")
            validation = await self.validate_with_ai(trade_params)
            trade_params["ai_validation"] = validation
            self.logger.info(
                "AI validation successful: risk_level=%.2f market_alignment=%.2f",
                validation.get("risk_assessment", {}).get("risk_level", 0),
                validation.get("validation_metrics", {}).get(
                    "market_conditions_alignment", 0
                ),
            )
        except TradingError as e:
            self.logger.error("AI validation failed with TradingError: %s", str(e))
            raise e
        except Exception as e:
            self.logger.warning(
                "AI validation failed with unexpected error: %s", str(e)
            )
            trade_params["ai_validation"] = {"error": str(e)}

        trade_id = f"trade_{int(datetime.now().timestamp())}"
        trade = {
            "id": trade_id,
            "params": trade_params,
            "status": "pending",
            "timestamp": datetime.now().isoformat(),
            "wallet": self.wallet_manager.get_public_key(),
        }

        if trade_params.get("use_go_executor", True):  # Default to using Go executor
            from .go_executor_client import execute_trade_in_go

            try:
                self.logger.info("Executing trade via Go executor: id=%s", trade_id)
                trade_result = await execute_trade_in_go(trade)
                self.active_trades[trade_id] = trade_result
                self.logger.info(
                    "Trade executed successfully: id=%s status=%s price=%.2f amount=%.2f",
                    trade_result["id"],
                    trade_result["status"],
                    trade_result.get("executed_price", 0),
                    trade_result.get("executed_amount", 0),
                )
                return trade_result
            except TradingError as e:
                self.logger.error(
                    "Trade execution failed: id=%s error=%s", trade_id, str(e)
                )
                trade["status"] = "failed"
                trade["error"] = str(e)
                self.active_trades[trade_id] = trade
                return trade

        self.active_trades[trade_id] = trade
        return trade

    async def cancel_trade(self, trade_id: str) -> bool:
        self.logger.info("Cancelling trade: id=%s", trade_id)
        if trade_id not in self.active_trades:
            self.logger.warning("Trade not found for cancellation: id=%s", trade_id)
            return False

        trade = self.active_trades[trade_id]
        trade["status"] = "cancelled"
        trade["cancelled_at"] = datetime.now().isoformat()

        self.trade_history.append(trade)
        del self.active_trades[trade_id]
        self.logger.info(
            "Trade cancelled successfully: id=%s cancelled_at=%s",
            trade_id,
            trade["cancelled_at"],
        )
        return True

    async def get_trade_status(self, trade_id: str) -> Optional[Dict[str, Any]]:
        self.logger.info("Getting trade status: id=%s", trade_id)
        try:
            if trade_id not in self.active_trades:
                self.logger.debug(
                    "Trade not found in active orders, checking history: id=%s",
                    trade_id,
                )
                return next(
                    (trade for trade in self.trade_history if trade["id"] == trade_id),
                    None,
                )

            try:
                status = await self.grpc_client.get_order_status(trade_id)
                trade = self.active_trades.get(trade_id)
                if trade:
                    self.logger.debug(
                        "Updating trade status: id=%s status=%s filled=%.2f price=%.2f",
                        trade_id,
                        status["status"],
                        status["filled_amount"],
                        status["average_price"],
                    )
                    trade.update(
                        {
                            "status": status["status"],
                            "filled_amount": status["filled_amount"],
                            "average_price": status["average_price"],
                        }
                    )
                    if status["status"] not in ["pending", "executing"]:
                        self.logger.info(
                            "Trade completed: id=%s status=%s",
                            trade_id,
                            status["status"],
                        )
                        self.trade_history.append(trade)
                        del self.active_trades[trade_id]
                return trade
            except Exception as e:
                self.logger.error("Failed to get order status: %s", str(e))
                return self.active_trades.get(trade_id)
        except Exception as e:
            self.logger.error("Error in get_trade_status: %s", str(e))
            return None

    def get_active_trades(self) -> List[Dict[str, Any]]:
        """Returns a list of currently active trades."""
        active_trades = list(self.active_trades.values())
        self.logger.debug("Retrieved %d active trades", len(active_trades))
        return active_trades

    def get_trade_history(self) -> List[Dict[str, Any]]:
        """Returns the complete trade history."""
        self.logger.debug("Retrieved trade history: %d trades", len(self.trade_history))
        return self.trade_history

    async def start(self) -> bool:
        self.logger.info("Starting trade executor")
        if not await super().start():
            self.logger.error("Failed to start base executor")
            return False

        if not self.wallet_manager.is_initialized():
            self.logger.error("Failed to start: wallet not initialized")
            self.status = "error"
            self.last_update = datetime.now().isoformat()
            return False

        await self.executor_pool.initialize()
        self.logger.info("Trade executor started successfully")
        return True

    async def stop(self) -> bool:
        self.logger.info(
            "Stopping trade executor, cancelling %d active trades",
            len(self.active_trades),
        )
        for trade_id in list(self.active_trades.keys()):
            await self.cancel_trade(trade_id)
        await self.executor_pool.close()
        result = await super().stop()
        self.logger.info("Trade executor stopped: success=%s", result)
        return result

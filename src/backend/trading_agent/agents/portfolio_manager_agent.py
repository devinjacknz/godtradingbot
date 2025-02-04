from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from src.shared.config.tenant_config import TenantConfig
from src.shared.db.database_manager import DatabaseManager
from src.shared.models.alerts import Alert, AlertLevel
from src.shared.models.deepseek import DeepSeek1_5B
from src.shared.models.trading import Portfolio, Position, Trade
from src.shared.utils.fallback_manager import FallbackManager

from .base_agent import BaseAgent


class PortfolioManagerAgent(BaseAgent):
    """资金管理代理,负责资产配置和仓位管理"""

    def __init__(self, agent_id: str, name: str, config: Dict[str, Any]):
        super().__init__(agent_id, name, config)
        self.portfolio: Optional[Portfolio] = None
        self.position_sizing: Dict[str, float] = {}  # 各资产的目标仓位
        self.risk_weights: Dict[str, float] = {}  # 风险权重
        self.rebalance_threshold = 0.1  # 再平衡阈值
        self.tenant_config = TenantConfig()  # 租户配置
        self.min_order_size = config.get("min_order_size", 0.01)
        self.max_position_size = config.get("max_position_size", 1.0)
        self.position_config = config.get(
            "position_config",
            {
                "base_size": 1000,
                "size_multiplier": 1.0,
                "max_position_percent": 0.2,
                "risk_based_sizing": True,
                "volatility_adjustment": True,
                "staged_entry": False,
                "entry_stages": [0.5, 0.3, 0.2],
                "profit_targets": [2.0, 3.0, 5.0],
                "size_per_stage": [0.2, 0.25, 0.2],
                "per_token_limits": {},
            },
        )
        self.model = DeepSeek1_5B(quantized=True)

        class LegacyPortfolioSystem:
            async def process(self, request: str) -> Dict[str, Any]:
                return {"text": '{"recommended_position_size": 0.1}', "confidence": 0.5}

        self.fallback_manager = FallbackManager(self.model, LegacyPortfolioSystem())

    async def start(self):
        self.status = "active"
        self.last_update = datetime.now().isoformat()

    async def stop(self):
        self.status = "inactive"
        self.last_update = datetime.now().isoformat()

    async def update_config(self, new_config: Dict[str, Any]):
        self.config = new_config
        self.min_order_size = new_config.get("min_order_size", self.min_order_size)
        self.max_position_size = new_config.get(
            "max_position_size", self.max_position_size
        )
        self.rebalance_threshold = new_config.get(
            "rebalance_threshold", self.rebalance_threshold
        )

        if "position_config" in new_config:
            self.position_config.update(new_config["position_config"])

        # Update per-token limits while preserving existing configs
        if "per_token_limits" in new_config.get("position_config", {}):
            self.position_config["per_token_limits"].update(
                new_config["position_config"]["per_token_limits"]
            )

        self.last_update = datetime.now().isoformat()

    async def generate_orders(
        self, signals: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not hasattr(self, "db_manager"):
            self.db_manager = DatabaseManager(
                mongodb_url=self.config["mongodb_url"],
                postgres_url=self.config["postgres_url"],
            )

        # Get AI-driven portfolio recommendations
        signals_text = "\n".join(
            [
                f"{s['symbol']}: strength={s.get('signal_strength', 0)}, risk={s.get('risk_level', 'medium')}"
                for s in signals
            ]
        )
        prompt = f"Analyze these trading signals and recommend position adjustments:\n{signals_text}\nOutput JSON with symbol and recommended_position_size (0-1):"

        cached_recommendation = self.cache.get(
            f"portfolio_recommendation:{hash(signals_text)}"
        )
        if not cached_recommendation:
            recommendation = await self.fallback_manager.execute(prompt)
            if recommendation:
                self.cache.set(
                    f"portfolio_recommendation:{hash(signals_text)}", recommendation
                )

        orders = []
        for signal in signals:
            symbol = signal["symbol"]
            current_position = self.portfolio.positions.get(
                symbol, Position(symbol=symbol, size=0, entry_price=0, current_price=0)
            )

            # Apply custom position sizing based on token-specific config
            token_config = self.position_config["per_token_limits"].get(symbol, {})
            base_size = token_config.get("base_size", self.position_config["base_size"])
            size_multiplier = token_config.get(
                "size_multiplier", self.position_config["size_multiplier"]
            )
            max_position_percent = token_config.get(
                "max_position_percent", self.position_config["max_position_percent"]
            )

            # Calculate target position using custom sizing rules
            position_size = base_size * size_multiplier
            max_size = self.max_position_size * max_position_percent
            target_position = min(position_size, max_size)

            # Apply risk-based sizing if enabled
            if self.position_config["risk_based_sizing"]:
                risk_factor = signal.get("risk_level_numeric", 0.5)
                target_position *= 1 - risk_factor

            # Apply volatility adjustment if enabled
            if self.position_config["volatility_adjustment"]:
                volatility = signal.get("volatility", 0.5)
                target_position *= max(0.2, 1 - volatility)

            if abs(target_position - current_position.size) < self.rebalance_threshold:
                continue

            order_size = target_position - current_position.size
            if abs(order_size) < self.min_order_size:
                continue

            if abs(target_position) > self.max_position_size:
                order_size = np.sign(order_size) * (
                    self.max_position_size - abs(current_position.size)
                )

            order = {
                "symbol": symbol,
                "side": "buy" if order_size > 0 else "sell",
                "size": abs(order_size),
                "type": "market",
                "timestamp": datetime.now().isoformat(),
                "status": "pending",
                "meta_info": {
                    "signal_strength": signal.get("signal_strength", 0),
                    "risk_level": signal.get("risk_level", "medium"),
                    "current_position": current_position.size,
                    "target_position": target_position,
                },
            }
            orders.append(order)

            # Store order in MongoDB
            await self.db_manager.mongodb.orders.insert_one(order)

        return orders

    async def initialize_portfolio(self, initial_capital: float):
        """初始化投资组合

        Args:
            initial_capital: 初始资金
        """
        self.portfolio = Portfolio(
            total_value=initial_capital,
            cash=initial_capital,
            positions={},
            last_update=datetime.now(),
        )

    async def calculate_position_size(self, symbol: str, price: float) -> float:
        """计算目标仓位规模

        Args:
            symbol: 交易对
            price: 当前价格

        Returns:
            float: 目标仓位规模
        """
        if not self.portfolio:
            return 0.0

        # 获取目标仓位比例
        target_weight = self.position_sizing.get(symbol, 0.0)

        # 计算目标仓位价值
        target_value = self.portfolio.total_value * target_weight

        # 考虑风险权重调整
        risk_weight = self.risk_weights.get(symbol, 1.0)
        adjusted_value = target_value * risk_weight

        # 转换为数量
        return adjusted_value / price if price > 0 else 0.0

    async def check_rebalance_needed(self, symbol: str) -> bool:
        """检查是否需要再平衡

        Args:
            symbol: 交易对

        Returns:
            bool: 是否需要再平衡
        """
        if not self.portfolio or symbol not in self.portfolio.positions:
            return False

        current_position = self.portfolio.positions[symbol]
        current_weight = (
            current_position.size * current_position.current_price
        ) / self.portfolio.total_value
        target_weight = self.position_sizing.get(symbol, 0.0)

        return abs(current_weight - target_weight) > self.rebalance_threshold

    async def update_portfolio(self, trade: Trade):
        """更新投资组合

        Args:
            trade: 成交信息
        """
        if not self.portfolio:
            return

        # 更新现金
        trade_value = trade.amount * trade.price
        if trade.side == "buy":
            self.portfolio.cash -= trade_value
        else:
            self.portfolio.cash += trade_value

        # 更新持仓
        symbol = trade.symbol
        if symbol not in self.portfolio.positions:
            self.portfolio.positions[symbol] = Position(
                symbol=symbol,
                size=0,
                entry_price=0,
                current_price=trade.price,
                unrealized_pnl=0,
                open_time=datetime.now(),
            )

        position = self.portfolio.positions[symbol]
        if trade.side == "buy":
            # 更新持仓均价
            total_value = position.size * position.entry_price + trade_value
            total_size = position.size + trade.amount
            position.entry_price = total_value / total_size if total_size > 0 else 0
            position.size = total_size
        else:
            position.size -= trade.amount
            if position.size <= 0:
                del self.portfolio.positions[symbol]

        # 更新总价值
        self.portfolio.total_value = self.portfolio.cash + sum(
            pos.size * pos.current_price for pos in self.portfolio.positions.values()
        )

        self.portfolio.last_update = datetime.now()

    async def get_portfolio_metrics(self) -> Dict:
        """获取投资组合指标"""
        if not self.portfolio:
            return {}

        total_positions = len(self.portfolio.positions)
        total_exposure = sum(
            abs(pos.size * pos.current_price)
            for pos in self.portfolio.positions.values()
        )

        return {
            "total_value": self.portfolio.total_value,
            "cash_ratio": self.portfolio.cash / self.portfolio.total_value,
            "total_positions": total_positions,
            "total_exposure": total_exposure,
            "leverage": (
                total_exposure / self.portfolio.total_value
                if self.portfolio.total_value > 0
                else 0
            ),
            "position_concentration": self._calculate_concentration(),
            "last_update": self.portfolio.last_update,
        }

    def _calculate_concentration(self) -> float:
        """计算持仓集中度(Herfindahl指数)"""
        if not self.portfolio or not self.portfolio.positions:
            return 0.0

        weights = [
            (pos.size * pos.current_price) / self.portfolio.total_value
            for pos in self.portfolio.positions.values()
        ]

        return sum(w * w for w in weights)  # 值越大表示集中度越高

    async def optimize_portfolio(self):
        """优化投资组合配置"""
        if not self.portfolio:
            return

        # 获取风险预算
        risk_budget = self.tenant_config.get_risk_budget()

        # 计算新的目标权重
        total_risk = sum(self.risk_weights.values())
        if total_risk > 0:
            self.position_sizing = {
                symbol: (weight / total_risk) * risk_budget
                for symbol, weight in self.risk_weights.items()
            }

        # 检查是否需要再平衡
        for symbol in self.portfolio.positions:
            if await self.check_rebalance_needed(symbol):
                # TODO: 生成再平衡交易建议
                pass

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.shared.cache.hybrid_cache import HybridCache
from src.shared.config.tenant_config import TenantConfig
from src.shared.models.deepseek import DeepSeek1_5B
from src.shared.models.market_data import OHLCV
from src.shared.models.trading import Portfolio, Position, Trade
from src.shared.monitor.metrics import track_inference_time
from src.shared.utils.batch_processor import BatchProcessor
from src.shared.utils.fallback_manager import FallbackManager

from .base_agent import BaseAgent


class ExecutionBatchProcessor(BatchProcessor[Dict[str, Any], Dict[str, Any]]):
    def __init__(self, agent):
        super().__init__(max_batch=16, timeout=50)
        self.agent = agent

    async def process(self, orders: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        return await self._process_items(orders)

    async def _process_items(self, items: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        results = []
        for order in items:
            try:
                prompt = f"""优化订单执行：
                订单ID：{order.get('id', '')}
                订单量：{order.get('size', 0)}
                市场深度：{order.get('depth', 0)}
                波动率：{order.get('volatility', 0)}%
                
                输出格式：
                {{
                    "slices": "拆分次数",
                    "intervals": "时间间隔",
                    "price_tolerance": "价格容忍度"
                }}"""
                result = await self.agent.model.generate(prompt)
                results.append(result)
            except Exception as e:
                logging.error(f"Error processing order: {str(e)}")
                results.append(
                    {"slices": 1, "intervals": "60s", "price_tolerance": "0.1%"}
                )
        return results


class ExecutionOptimizerAgent(BaseAgent):
    def __init__(self, agent_id: str, name: str, config: Dict[str, Any]):
        super().__init__(agent_id, name, config)
        try:
            self.model = DeepSeek1_5B(quantized=True)
        except Exception as e:
            logging.warning(f"Failed to initialize DeepSeek model: {str(e)}")
            from ..tests.mocks import MockDeepSeekModel

            self.model = MockDeepSeekModel()

        self.cache = HybridCache()
        self.batch_processor = ExecutionBatchProcessor(self)

        class LegacyExecutionSystem:
            async def process(
                self, orders: list[Dict[str, Any]]
            ) -> list[Dict[str, Any]]:
                return [
                    {"slices": 1, "intervals": "60s", "price_tolerance": "0.1%"}
                    for _ in orders
                ]

        self.fallback_manager = FallbackManager(
            self.batch_processor, LegacyExecutionSystem()
        )

    @track_inference_time
    async def optimize_execution(self, order: Dict[str, Any]) -> Dict[str, Any]:
        cache_key = f"execution_plan:{order['id']}"
        if cached := self.cache.get(cache_key):
            return cached

        try:
            prompt = f"""优化订单执行：
            订单量：{order.get('size', 0)}
            市场深度：{order.get('depth', 0)}
            波动率：{order.get('volatility', 0)}%
            
            输出格式：
            {{
                "slices": "拆分次数",
                "intervals": "时间间隔",
                "price_tolerance": "价格容忍度"
            }}"""
            result = await self.batch_processor.process([order])
            if result:
                result = result[0]
                self.cache.set(cache_key, result)
                return result
            raise Exception("Failed to generate execution plan")
        except Exception as e:
            logging.error(f"Error optimizing execution: {str(e)}")
            return {"slices": 1, "intervals": "60s", "price_tolerance": "0.1%"}

    async def optimize_batch(
        self, orders: list[Dict[str, Any]]
    ) -> list[Dict[str, Any]]:
        try:
            return await self.batch_processor.process(orders)
        except Exception as e:
            logging.error(f"Error optimizing batch: {str(e)}")
            return [
                {"slices": 1, "intervals": "60s", "price_tolerance": "0.1%"}
                for _ in orders
            ]

    async def start(self):
        self.status = "active"
        self.last_update = datetime.now().isoformat()

    async def stop(self):
        self.status = "inactive"
        self.last_update = datetime.now().isoformat()

    async def update_config(self, new_config: Dict[str, Any]):
        self.config.update(new_config)
        self.last_update = datetime.now().isoformat()


class BacktestEngine:
    """回测引擎"""

    def __init__(self, config: Dict):
        self.config = config
        self.portfolio = Portfolio(
            total_value=config.get("initial_capital", 100000),
            cash=config.get("initial_capital", 100000),
            positions={},
            last_update=datetime.now(),
        )
        self.trades: List[Trade] = []
        self.metrics: Dict = {}
        self.market_data: Dict[str, pd.DataFrame] = {}

    def load_market_data(self, data: Dict[str, List[OHLCV]]):
        """加载市场数据

        Args:
            data: 市场数据,按交易对组织
        """
        for symbol, ohlcv_list in data.items():
            df = pd.DataFrame(
                [
                    {
                        "timestamp": bar.timestamp,
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "volume": bar.volume,
                    }
                    for bar in ohlcv_list
                ]
            )
            df.set_index("timestamp", inplace=True)
            self.market_data[symbol] = df

    def simulate_trade(self, trade: Trade) -> bool:
        """模拟交易执行

        Args:
            trade: 交易信息

        Returns:
            bool: 是否执行成功
        """
        symbol = trade.symbol
        if symbol not in self.market_data:
            return False

        # 获取当前价格
        current_price = self.market_data[symbol].loc[trade.timestamp, "close"]
        trade_value = trade.amount * current_price

        # 检查资金是否足够
        if trade.side == "buy" and trade_value > self.portfolio.cash:
            return False

        # 检查持仓是否足够
        if trade.side == "sell":
            position = self.portfolio.positions.get(symbol)
            if not position or position.size < trade.amount:
                return False

        # 更新投资组合
        if trade.side == "buy":
            self.portfolio.cash -= trade_value
            if symbol not in self.portfolio.positions:
                self.portfolio.positions[symbol] = Position(
                    symbol=symbol,
                    size=0,
                    entry_price=0,
                    current_price=current_price,
                    unrealized_pnl=0,
                    open_time=trade.timestamp,
                )
            position = self.portfolio.positions[symbol]
            position.size += trade.amount
            position.entry_price = (
                position.entry_price * (position.size - trade.amount)
                + current_price * trade.amount
            ) / position.size
        else:
            self.portfolio.cash += trade_value
            position = self.portfolio.positions[symbol]
            position.size -= trade.amount
            if position.size <= 0:
                del self.portfolio.positions[symbol]

        # 记录交易
        self.trades.append(trade)
        return True

    def update_portfolio_value(self, timestamp: datetime):
        """更新投资组合价值

        Args:
            timestamp: 当前时间戳
        """
        total_value = self.portfolio.cash

        for symbol, position in self.portfolio.positions.items():
            current_price = self.market_data[symbol].loc[timestamp, "close"]
            position.current_price = current_price
            position.unrealized_pnl = (
                current_price - position.entry_price
            ) * position.size
            total_value += position.size * current_price

        self.portfolio.total_value = total_value
        self.portfolio.last_update = timestamp

    def calculate_metrics(self):
        """计算回测指标"""
        if not self.trades:
            return

        # 计算收益率序列
        returns = []
        timestamps = []
        portfolio_values = []
        current_value = self.config["initial_capital"]

        for trade in self.trades:
            pnl = trade.pnl if hasattr(trade, "pnl") else 0
            current_value += pnl
            returns.append(pnl / current_value)
            timestamps.append(trade.timestamp)
            portfolio_values.append(current_value)

        returns = np.array(returns)

        # 计算各项指标
        total_return = (current_value - self.config["initial_capital"]) / self.config[
            "initial_capital"
        ]
        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        max_drawdown = self._calculate_max_drawdown(portfolio_values)
        win_rate = len([t for t in self.trades if t.pnl > 0]) / len(self.trades)

        self.metrics = {
            "total_return": total_return,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "total_trades": len(self.trades),
            "avg_trade_pnl": np.mean([t.pnl for t in self.trades if hasattr(t, "pnl")]),
            "volatility": np.std(returns) * np.sqrt(252),  # 年化波动率
            "beta": self._calculate_beta(returns, timestamps),
        }

    def _calculate_sharpe_ratio(self, returns: np.ndarray) -> float:
        """计算夏普比率"""
        if len(returns) < 2:
            return 0.0
        return np.mean(returns) / np.std(returns) * np.sqrt(252)

    def _calculate_max_drawdown(self, values: List[float]) -> float:
        """计算最大回撤"""
        peak = values[0]
        max_dd = 0

        for value in values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)

        return max_dd

    def _calculate_beta(self, returns: np.ndarray, timestamps: List[datetime]) -> float:
        """计算Beta值"""
        if len(returns) < 2:
            return 0.0

        # 获取市场收益率
        market_returns = []
        for t in timestamps:
            # 这里使用第一个交易对作为市场基准
            symbol = next(iter(self.market_data))
            market_return = (
                self.market_data[symbol].loc[t, "close"]
                / self.market_data[symbol].shift(1).loc[t, "close"]
                - 1
            )
            market_returns.append(market_return)

        market_returns = np.array(market_returns)

        # 计算Beta
        covariance = np.cov(returns, market_returns)[0][1]
        market_variance = np.var(market_returns)

        return covariance / market_variance if market_variance > 0 else 0.0

    def get_trade_history(self) -> pd.DataFrame:
        """获取交易历史"""
        if not self.trades:
            return pd.DataFrame()

        return pd.DataFrame(
            [
                {
                    "timestamp": t.timestamp,
                    "symbol": t.symbol,
                    "side": t.side,
                    "amount": t.amount,
                    "price": t.price,
                    "pnl": getattr(t, "pnl", 0),
                }
                for t in self.trades
            ]
        )

    def plot_results(self):
        """绘制回测结果"""
        if not self.trades:
            return

        import matplotlib.pyplot as plt

        # 绘制投资组合价值
        plt.figure(figsize=(12, 6))
        plt.plot(
            [t.timestamp for t in self.trades],
            [t.portfolio_value for t in self.trades if hasattr(t, "portfolio_value")],
            label="Portfolio Value",
        )
        plt.title("Portfolio Value Over Time")
        plt.xlabel("Time")
        plt.ylabel("Value")
        plt.legend()
        plt.grid(True)
        plt.show()

        # 绘制收益分布
        plt.figure(figsize=(12, 6))
        plt.hist([t.pnl for t in self.trades if hasattr(t, "pnl")], bins=50)
        plt.title("PnL Distribution")
        plt.xlabel("PnL")
        plt.ylabel("Frequency")
        plt.grid(True)
        plt.show()

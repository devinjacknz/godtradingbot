import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import numpy as np
from prometheus_client import Counter, Gauge, Histogram


class GasPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class GasMetrics:
    """Gas指标"""

    current_base_fee: Gauge
    priority_fee: Gauge
    total_gas_cost: Counter
    transaction_count: Counter
    estimation_accuracy: Gauge
    optimization_savings: Counter


class GasManager:
    def __init__(self, config: Dict):
        self.config = config
        self.gas_history = []
        self.fee_estimates = {}
        self.pending_txs = {}

        # Gas指标
        self.metrics = GasMetrics(
            current_base_fee=Gauge("gas_current_base_fee", "Current base fee"),
            priority_fee=Gauge("gas_priority_fee", "Current priority fee"),
            total_gas_cost=Counter("gas_total_cost", "Total gas cost"),
            transaction_count=Counter(
                "gas_transaction_count", "Number of transactions"
            ),
            estimation_accuracy=Gauge(
                "gas_estimation_accuracy", "Gas estimation accuracy"
            ),
            optimization_savings=Counter(
                "gas_optimization_savings", "Gas cost savings"
            ),
        )

        # Gas配置
        self.gas_limits = {
            "max_base_fee": config.get("max_base_fee", 500),
            "max_priority_fee": config.get("max_priority_fee", 50),
            "min_confidence": config.get("min_confidence", 0.8),
            "history_window": config.get("history_window", 1000),
            "update_interval": config.get("update_interval", 1),
        }

        # 初始化监控任务
        self.monitor_task = None

    async def start(self):
        """启动Gas管理系统"""
        self.monitor_task = asyncio.create_task(self._monitor_gas())

    async def stop(self):
        """停止Gas管理系统"""
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_gas(self):
        """Gas监控循环"""
        while True:
            try:
                # 更新Gas价格
                await self._update_gas_prices()

                # 优化待处理交易
                await self._optimize_pending_transactions()

                # 更新费用估算
                await self._update_fee_estimates()

                # 等待下一次更新
                await asyncio.sleep(self.gas_limits["update_interval"])

            except Exception as e:
                self.logger.error(f"Error in gas monitoring: {str(e)}")
                await asyncio.sleep(1)

    async def _update_gas_prices(self):
        """更新Gas价格"""
        try:
            # 获取当前区块Gas信息
            block_info = await self._get_latest_block_info()

            # 更新基础费用
            base_fee = block_info["base_fee_per_gas"]
            self.metrics.current_base_fee.set(base_fee)

            # 更新优先费用
            priority_fee = await self._estimate_priority_fee()
            self.metrics.priority_fee.set(priority_fee)

            # 更新历史数据
            self.gas_history.append(
                {
                    "timestamp": time.time(),
                    "base_fee": base_fee,
                    "priority_fee": priority_fee,
                    "block_number": block_info["number"],
                }
            )

            # 保持历史窗口大小
            if len(self.gas_history) > self.gas_limits["history_window"]:
                self.gas_history = self.gas_history[
                    -self.gas_limits["history_window"] :
                ]

        except Exception as e:
            self.logger.error(f"Error updating gas prices: {str(e)}")

    async def _estimate_priority_fee(self) -> float:
        """估算优先费用"""
        try:
            if not self.gas_history:
                return self.gas_limits["max_priority_fee"]

            recent_fees = [
                entry["priority_fee"] for entry in self.gas_history[-50:]  # 使用最近50个区块
            ]

            # 计算不同百分位的费用
            percentiles = np.percentile(recent_fees, [25, 50, 75, 90])

            # 根据网络拥堵程度选择百分位
            congestion = self._calculate_network_congestion()
            if congestion > 0.8:
                return percentiles[3]  # 90th percentile
            elif congestion > 0.6:
                return percentiles[2]  # 75th percentile
            elif congestion > 0.4:
                return percentiles[1]  # 50th percentile
            else:
                return percentiles[0]  # 25th percentile

        except Exception as e:
            self.logger.error(f"Error estimating priority fee: {str(e)}")
            return self.gas_limits["max_priority_fee"]

    def _calculate_network_congestion(self) -> float:
        """计算网络拥堵程度"""
        try:
            if not self.gas_history:
                return 0.5

            recent_base_fees = [
                entry["base_fee"] for entry in self.gas_history[-20:]  # 使用最近20个区块
            ]

            # 计算基础费用变化率
            fee_changes = np.diff(recent_base_fees) / recent_base_fees[:-1]

            # 计算拥堵分数 (0-1)
            congestion_score = np.mean(
                [
                    1 / (1 + np.exp(-10 * change))  # Sigmoid函数映射到0-1
                    for change in fee_changes
                ]
            )

            return congestion_score

        except Exception as e:
            self.logger.error(f"Error calculating network congestion: {str(e)}")
            return 0.5

    async def _optimize_pending_transactions(self):
        """优化待处理交易"""
        try:
            current_base_fee = self.metrics.current_base_fee._value.get()
            current_priority_fee = self.metrics.priority_fee._value.get()

            for tx_hash, tx_info in list(self.pending_txs.items()):
                # 检查是否需要加速
                if self._should_accelerate_transaction(tx_info):
                    new_fees = self._calculate_acceleration_fees(
                        tx_info, current_base_fee, current_priority_fee
                    )
                    await self._accelerate_transaction(tx_hash, new_fees)

                # 检查是否可以取消重发
                elif self._should_resubmit_transaction(tx_info):
                    await self._resubmit_transaction(tx_hash, tx_info)

        except Exception as e:
            self.logger.error(f"Error optimizing pending transactions: {str(e)}")

    def _should_accelerate_transaction(self, tx_info: Dict) -> bool:
        """判断是否需要加速交易"""
        try:
            # 检查交易优先级
            if tx_info["priority"] == GasPriority.URGENT:
                return True

            # 检查等待时间
            wait_time = time.time() - tx_info["submit_time"]
            if wait_time > tx_info["max_wait_time"]:
                return True

            # 检查确认块数
            if tx_info.get("confirmations", 0) < tx_info["required_confirmations"]:
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error checking transaction acceleration: {str(e)}")
            return False

    def _calculate_acceleration_fees(
        self, tx_info: Dict, current_base_fee: float, current_priority_fee: float
    ) -> Dict:
        """计算加速所需费用"""
        try:
            # 基础费用增加10-50%
            base_fee_multiplier = 1.1
            if tx_info["priority"] == GasPriority.URGENT:
                base_fee_multiplier = 1.5

            new_base_fee = min(
                current_base_fee * base_fee_multiplier, self.gas_limits["max_base_fee"]
            )

            # 优先费用增加20-100%
            priority_fee_multiplier = 1.2
            if tx_info["priority"] == GasPriority.URGENT:
                priority_fee_multiplier = 2.0

            new_priority_fee = min(
                current_priority_fee * priority_fee_multiplier,
                self.gas_limits["max_priority_fee"],
            )

            return {"base_fee": new_base_fee, "priority_fee": new_priority_fee}

        except Exception as e:
            self.logger.error(f"Error calculating acceleration fees: {str(e)}")
            return {"base_fee": current_base_fee, "priority_fee": current_priority_fee}

    async def _update_fee_estimates(self):
        """更新费用估算"""
        try:
            # 获取最近交易的实际费用
            recent_txs = [
                tx
                for tx in self.pending_txs.values()
                if tx.get("status") == "confirmed"
            ][-100:]

            if not recent_txs:
                return

            # 计算估算准确度
            estimation_errors = []
            for tx in recent_txs:
                estimated_total = (
                    tx["estimated_base_fee"] + tx["estimated_priority_fee"]
                )
                actual_total = tx["actual_base_fee"] + tx["actual_priority_fee"]
                error = abs(estimated_total - actual_total) / actual_total
                estimation_errors.append(error)

            accuracy = 1 - np.mean(estimation_errors)
            self.metrics.estimation_accuracy.set(accuracy)

            # 计算优化节省
            total_savings = sum(
                tx["estimated_total"] - tx["actual_total"]
                for tx in recent_txs
                if tx["estimated_total"] > tx["actual_total"]
            )
            self.metrics.optimization_savings.inc(total_savings)

        except Exception as e:
            self.logger.error(f"Error updating fee estimates: {str(e)}")

    def get_gas_status(self) -> Dict:
        """获取Gas状态摘要"""
        return {
            "current_base_fee": self.metrics.current_base_fee._value.get(),
            "current_priority_fee": self.metrics.priority_fee._value.get(),
            "network_congestion": self._calculate_network_congestion(),
            "estimation_accuracy": self.metrics.estimation_accuracy._value.get(),
            "pending_transactions": len(self.pending_txs),
            "total_savings": self.metrics.optimization_savings._value.get(),
        }

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import numpy as np
from prometheus_client import Counter, Gauge, Histogram


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskMetrics:
    """风控指标"""

    total_exposure: Gauge
    margin_ratio: Gauge
    risk_level: Gauge
    position_count: Gauge
    liquidation_risk: Gauge
    circuit_breaker_triggers: Counter
    risk_checks: Counter


class RiskManager:
    def __init__(self, config: Dict):
        self.config = config
        self.positions = {}
        self.strategy_risks = {}
        self.circuit_breakers = {}

        # 风控指标
        self.metrics = RiskMetrics(
            total_exposure=Gauge("risk_total_exposure", "Total position exposure"),
            margin_ratio=Gauge("risk_margin_ratio", "Current margin ratio"),
            risk_level=Gauge("risk_level", "Current risk level"),
            position_count=Gauge("risk_position_count", "Number of open positions"),
            liquidation_risk=Gauge("risk_liquidation_risk", "Liquidation risk score"),
            circuit_breaker_triggers=Counter(
                "risk_circuit_breaker_triggers", "Circuit breaker triggers"
            ),
            risk_checks=Counter("risk_checks", "Number of risk checks performed"),
        )

        # 风控配置
        self.risk_limits = {
            "max_total_exposure": config.get("max_total_exposure", 1000000),
            "min_margin_ratio": config.get("min_margin_ratio", 0.1),
            "max_position_count": config.get("max_position_count", 100),
            "circuit_breaker_threshold": config.get("circuit_breaker_threshold", 0.1),
            "risk_check_interval": config.get("risk_check_interval", 1),
        }

        # 初始化监控任务
        self.monitor_task = None

    async def start(self):
        """启动风控系统"""
        self.monitor_task = asyncio.create_task(self._monitor_risks())

    async def stop(self):
        """停止风控系统"""
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_risks(self):
        """风险监控循环"""
        while True:
            try:
                # 更新风险指标
                await self._update_risk_metrics()

                # 检查风险限制
                await self._check_risk_limits()

                # 更新熔断机制状态
                await self._update_circuit_breakers()

                # 等待下一次检查
                await asyncio.sleep(self.risk_limits["risk_check_interval"])

            except Exception as e:
                self.logger.error(f"Error in risk monitoring: {str(e)}")
                await asyncio.sleep(1)

    async def _update_risk_metrics(self):
        """更新风险指标"""
        try:
            # 计算总敞口
            total_exposure = sum(
                abs(position["size"] * position["price"])
                for position in self.positions.values()
            )
            self.metrics.total_exposure.set(total_exposure)

            # 计算保证金率
            total_margin = sum(
                position["margin"] for position in self.positions.values()
            )
            if total_exposure > 0:
                margin_ratio = total_margin / total_exposure
                self.metrics.margin_ratio.set(margin_ratio)

            # 更新持仓数量
            self.metrics.position_count.set(len(self.positions))

            # 计算清算风险
            liquidation_risk = self._calculate_liquidation_risk()
            self.metrics.liquidation_risk.set(liquidation_risk)

            # 更新风险等级
            risk_level = self._calculate_risk_level(
                total_exposure, margin_ratio, liquidation_risk
            )
            self.metrics.risk_level.set(risk_level.value)

            # 更新检查计数
            self.metrics.risk_checks.inc()

        except Exception as e:
            self.logger.error(f"Error updating risk metrics: {str(e)}")

    def _calculate_liquidation_risk(self) -> float:
        """计算清算风险分数"""
        try:
            if not self.positions:
                return 0.0

            risk_scores = []
            for position in self.positions.values():
                # 计算到清算价格的距离
                current_price = position["price"]
                liquidation_price = position["liquidation_price"]
                price_distance = abs(current_price - liquidation_price) / current_price

                # 计算风险分数 (0-1)
                risk_score = 1 - min(1, price_distance / 0.1)  # 10%价格距离内线性计算
                risk_scores.append(risk_score)

            # 返回最高风险分数
            return max(risk_scores) if risk_scores else 0.0

        except Exception as e:
            self.logger.error(f"Error calculating liquidation risk: {str(e)}")
            return 1.0  # 错误时返回最高风险

    def _calculate_risk_level(
        self, total_exposure: float, margin_ratio: float, liquidation_risk: float
    ) -> RiskLevel:
        """计算综合风险等级"""
        try:
            # 计算风险因子
            exposure_factor = min(
                1, total_exposure / self.risk_limits["max_total_exposure"]
            )
            margin_factor = 1 - margin_ratio / self.risk_limits["min_margin_ratio"]

            # 综合风险分数 (0-1)
            risk_score = max(
                exposure_factor * 0.4, margin_factor * 0.3, liquidation_risk * 0.3
            )

            # 确定风险等级
            if risk_score < 0.3:
                return RiskLevel.LOW
            elif risk_score < 0.6:
                return RiskLevel.MEDIUM
            elif risk_score < 0.8:
                return RiskLevel.HIGH
            else:
                return RiskLevel.CRITICAL

        except Exception as e:
            self.logger.error(f"Error calculating risk level: {str(e)}")
            return RiskLevel.CRITICAL

    async def _check_risk_limits(self):
        """检查风险限制"""
        try:
            current_metrics = {
                "total_exposure": self.metrics.total_exposure._value.get(),
                "margin_ratio": self.metrics.margin_ratio._value.get(),
                "position_count": self.metrics.position_count._value.get(),
                "liquidation_risk": self.metrics.liquidation_risk._value.get(),
            }

            # 检查是否超过限制
            if (
                current_metrics["total_exposure"]
                > self.risk_limits["max_total_exposure"]
            ):
                await self._trigger_risk_action("exposure_limit")

            if current_metrics["margin_ratio"] < self.risk_limits["min_margin_ratio"]:
                await self._trigger_risk_action("margin_limit")

            if (
                current_metrics["position_count"]
                > self.risk_limits["max_position_count"]
            ):
                await self._trigger_risk_action("position_limit")

            if current_metrics["liquidation_risk"] > 0.8:  # 80%清算风险
                await self._trigger_risk_action("liquidation_risk")

        except Exception as e:
            self.logger.error(f"Error checking risk limits: {str(e)}")

    async def _trigger_risk_action(self, risk_type: str):
        """触发风险控制动作"""
        try:
            # 记录风险事件
            self.logger.warning(f"Risk limit breached: {risk_type}")

            # 更新熔断器状态
            self.circuit_breakers[risk_type] = {
                "triggered_at": time.time(),
                "cool_down": self.config.get("circuit_breaker_cooldown", 300),  # 5分钟冷却
            }

            # 增加触发计数
            self.metrics.circuit_breaker_triggers.inc()

            # 执行风险控制动作
            if risk_type in ["exposure_limit", "margin_limit"]:
                await self._reduce_positions()
            elif risk_type == "liquidation_risk":
                await self._handle_liquidation_risk()

        except Exception as e:
            self.logger.error(f"Error triggering risk action: {str(e)}")

    async def _reduce_positions(self):
        """减少持仓"""
        try:
            # 按风险等级排序持仓
            sorted_positions = sorted(
                self.positions.items(), key=lambda x: x[1]["risk_score"], reverse=True
            )

            # 逐个减少高风险持仓
            for position_id, position in sorted_positions:
                if position["size"] > position["min_size"]:
                    # 计算减仓数量
                    reduction = position["size"] * 0.5  # 减少50%

                    # 执行减仓
                    await self._execute_reduction(position_id, reduction)

        except Exception as e:
            self.logger.error(f"Error reducing positions: {str(e)}")

    async def _handle_liquidation_risk(self):
        """处理清算风险"""
        try:
            # 识别高风险持仓
            high_risk_positions = [
                (pid, pos)
                for pid, pos in self.positions.items()
                if self._calculate_position_risk(pos) > 0.8
            ]

            # 对高风险持仓采取行动
            for position_id, position in high_risk_positions:
                # 增加保证金或减少持仓
                if position["can_add_margin"]:
                    await self._add_margin(position_id)
                else:
                    await self._execute_reduction(position_id, position["size"] * 0.7)

        except Exception as e:
            self.logger.error(f"Error handling liquidation risk: {str(e)}")

    async def _update_circuit_breakers(self):
        """更新熔断器状态"""
        try:
            current_time = time.time()

            # 检查并重置已冷却的熔断器
            for circuit_type, state in list(self.circuit_breakers.items()):
                if current_time - state["triggered_at"] > state["cool_down"]:
                    del self.circuit_breakers[circuit_type]
                    self.logger.info(f"Circuit breaker reset: {circuit_type}")

        except Exception as e:
            self.logger.error(f"Error updating circuit breakers: {str(e)}")

    def get_risk_status(self) -> Dict:
        """获取风险状态摘要"""
        return {
            "risk_level": RiskLevel(self.metrics.risk_level._value.get()).name,
            "total_exposure": self.metrics.total_exposure._value.get(),
            "margin_ratio": self.metrics.margin_ratio._value.get(),
            "position_count": self.metrics.position_count._value.get(),
            "liquidation_risk": self.metrics.liquidation_risk._value.get(),
            "circuit_breakers": {
                cb_type: {
                    "time_remaining": max(
                        0, state["cool_down"] - (time.time() - state["triggered_at"])
                    )
                }
                for cb_type, state in self.circuit_breakers.items()
            },
        }

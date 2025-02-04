import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import numpy as np
from prometheus_client import Counter, Gauge, Histogram


class StrategyState(Enum):
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class StrategyMetrics:
    execution_time: Histogram
    success_rate: Gauge
    error_count: Counter
    profit_loss: Gauge
    position_size: Gauge
    weight: Gauge


class StrategyExecutor:
    def __init__(self, config: Dict):
        self.config = config
        self.strategies = {}
        self.weights = {}
        self.performance_history = {}
        self.state = {}

        # 性能指标
        self.metrics = {
            "execution_latency": Histogram(
                "strategy_execution_latency",
                "Strategy execution latency",
                buckets=[0.01, 0.05, 0.1, 0.2, 0.5],
            ),
            "concurrent_strategies": Gauge(
                "concurrent_strategies", "Number of concurrent strategies"
            ),
            "weight_updates": Counter("weight_updates", "Strategy weight updates"),
        }

        # 初始化任务池
        self.task_pool = asyncio.Queue(maxsize=config.get("max_concurrent_tasks", 100))
        self.executor_task = None

    async def start(self):
        """启动策略执行器"""
        self.executor_task = asyncio.create_task(self._execute_strategies())

    async def stop(self):
        """停止策略执行器"""
        if self.executor_task:
            self.executor_task.cancel()
            try:
                await self.executor_task
            except asyncio.CancelledError:
                pass

    async def add_strategy(self, strategy_id: str, strategy: Dict):
        """添加新策略"""
        self.strategies[strategy_id] = strategy
        self.weights[strategy_id] = strategy.get("initial_weight", 1.0)
        self.state[strategy_id] = StrategyState.INITIALIZING
        self.performance_history[strategy_id] = []

        # 创建策略指标
        self.metrics[strategy_id] = StrategyMetrics(
            execution_time=Histogram(
                f"strategy_{strategy_id}_execution_time",
                "Strategy execution time",
                buckets=[0.01, 0.05, 0.1, 0.2, 0.5],
            ),
            success_rate=Gauge(
                f"strategy_{strategy_id}_success_rate", "Strategy success rate"
            ),
            error_count=Counter(
                f"strategy_{strategy_id}_error_count", "Strategy error count"
            ),
            profit_loss=Gauge(
                f"strategy_{strategy_id}_profit_loss", "Strategy profit/loss"
            ),
            position_size=Gauge(
                f"strategy_{strategy_id}_position_size", "Strategy position size"
            ),
            weight=Gauge(f"strategy_{strategy_id}_weight", "Strategy weight"),
        )

    async def _execute_strategies(self):
        """并发执行策略"""
        while True:
            try:
                # 获取活跃策略
                active_strategies = [
                    sid
                    for sid, state in self.state.items()
                    if state == StrategyState.RUNNING
                ]

                # 更新并发策略数
                self.metrics["concurrent_strategies"].set(len(active_strategies))

                # 创建策略执行任务
                tasks = []
                for strategy_id in active_strategies:
                    task = asyncio.create_task(
                        self._execute_single_strategy(strategy_id)
                    )
                    tasks.append(task)

                # 等待所有策略执行完成
                if tasks:
                    await asyncio.gather(*tasks)

                # 动态调整权重
                await self._adjust_weights()

                # 等待下一个执行周期
                await asyncio.sleep(self.config.get("execution_interval", 0.1))

            except Exception as e:
                self.logger.error(f"Error in strategy execution: {str(e)}")
                await asyncio.sleep(1)

    async def _execute_single_strategy(self, strategy_id: str):
        """执行单个策略"""
        try:
            start_time = time.time()

            # 获取策略配置
            strategy = self.strategies[strategy_id]
            weight = self.weights[strategy_id]

            # 执行策略逻辑
            result = await strategy["execute"](weight)

            # 更新性能指标
            execution_time = time.time() - start_time
            self.metrics[strategy_id].execution_time.observe(execution_time)
            self.metrics["execution_latency"].observe(execution_time)

            # 更新策略性能历史
            self.performance_history[strategy_id].append(
                {
                    "timestamp": time.time(),
                    "execution_time": execution_time,
                    "result": result,
                }
            )

            # 更新其他指标
            if result:
                self.metrics[strategy_id].success_rate.set(1)
                self.metrics[strategy_id].profit_loss.set(result.get("pnl", 0))
                self.metrics[strategy_id].position_size.set(result.get("position", 0))

        except Exception as e:
            self.metrics[strategy_id].error_count.inc()
            self.metrics[strategy_id].success_rate.set(0)
            self.logger.error(f"Error executing strategy {strategy_id}: {str(e)}")

    async def _adjust_weights(self):
        """动态调整策略权重"""
        try:
            # 计算每个策略的性能分数
            scores = {}
            for strategy_id in self.strategies:
                history = self.performance_history[strategy_id][-100:]  # 使用最近100次执行记录
                if not history:
                    continue

                # 计算性能指标
                success_rate = sum(1 for h in history if h["result"]) / len(history)
                avg_execution_time = np.mean([h["execution_time"] for h in history])
                avg_pnl = np.mean(
                    [h["result"].get("pnl", 0) for h in history if h["result"]]
                )

                # 计算综合得分
                score = (
                    success_rate * 0.4  # 成功率权重40%
                    + (1 - avg_execution_time / 0.2) * 0.3  # 执行时间权重30%
                    + (avg_pnl / 100) * 0.3  # 收益权重30%
                )
                scores[strategy_id] = max(0.1, min(1.0, score))  # 限制权重范围

            # 归一化权重
            total_score = sum(scores.values())
            if total_score > 0:
                for strategy_id, score in scores.items():
                    new_weight = score / total_score
                    old_weight = self.weights[strategy_id]

                    # 平滑权重调整
                    adjustment_rate = self.config.get("weight_adjustment_rate", 0.1)
                    self.weights[strategy_id] = (
                        old_weight * (1 - adjustment_rate)
                        + new_weight * adjustment_rate
                    )

                    # 更新权重指标
                    self.metrics[strategy_id].weight.set(self.weights[strategy_id])
                    self.metrics["weight_updates"].inc()

        except Exception as e:
            self.logger.error(f"Error adjusting weights: {str(e)}")

    def get_strategy_status(self, strategy_id: str) -> Dict:
        """获取策略状态"""
        return {
            "state": self.state[strategy_id].value,
            "weight": self.weights[strategy_id],
            "metrics": {
                "success_rate": self.metrics[strategy_id].success_rate._value.get(),
                "error_count": self.metrics[strategy_id].error_count._value.get(),
                "profit_loss": self.metrics[strategy_id].profit_loss._value.get(),
                "position_size": self.metrics[strategy_id].position_size._value.get(),
            },
        }

from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
from web3 import Web3

from src.shared.cache.hybrid_cache import HybridCache
from src.shared.config.tenant_config import TenantConfig
from src.shared.models.alerts import Alert, AlertLevel


class GasManager:
    """Gas费用管理器，实现EIP-1559动态费用调整"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cache = HybridCache()
        self.tenant_config = TenantConfig()
        self.w3 = Web3(Web3.HTTPProvider(config["eth_rpc_url"]))

        # Gas费用配置
        self.base_fee_multiplier = config.get("base_fee_multiplier", 1.125)
        self.max_priority_fee = config.get("max_priority_fee", 3.0)  # Gwei
        self.min_priority_fee = config.get("min_priority_fee", 1.0)  # Gwei
        self.gas_price_history: List[Dict] = []
        self.fee_stats: Dict[str, float] = {}

    async def estimate_gas_price(self, tx_type: str = "standard") -> Dict[str, float]:
        """估算Gas价格

        Args:
            tx_type: 交易类型 (standard/fast/urgent)

        Returns:
            Dict: Gas价格估算结果
        """
        # 检查缓存
        cache_key = f"gas_price:{tx_type}"
        if cached := self.cache.get(cache_key):
            return cached

        try:
            # 获取当前区块
            block = self.w3.eth.get_block("latest")
            base_fee = block["baseFeePerGas"] / 1e9  # 转换为Gwei

            # 根据交易类型调整系数
            multipliers = {"standard": 1.0, "fast": 1.2, "urgent": 1.5}
            fee_multiplier = multipliers.get(tx_type, 1.0)

            # 计算max_fee_per_gas
            max_fee = base_fee * self.base_fee_multiplier * fee_multiplier

            # 计算priority_fee
            priority_fee = self._calculate_priority_fee(tx_type)

            result = {
                "base_fee": base_fee,
                "max_fee_per_gas": max_fee,
                "max_priority_fee_per_gas": priority_fee,
                "estimated_cost": max_fee + priority_fee,
                "timestamp": datetime.now().isoformat(),
            }

            # 更新缓存
            self.cache.set(cache_key, result, ttl=30)  # 30秒缓存
            return result

        except Exception as e:
            # 使用历史数据作为fallback
            return self._get_fallback_gas_price(tx_type)

    def _calculate_priority_fee(self, tx_type: str) -> float:
        """计算优先费用

        Args:
            tx_type: 交易类型

        Returns:
            float: 优先费用(Gwei)
        """
        # 获取最近的优先费用数据
        recent_fees = [tx["priority_fee"] for tx in self.gas_price_history[-50:]]
        if not recent_fees:
            return self.min_priority_fee

        # 根据交易类型选择百分位
        percentiles = {"standard": 50, "fast": 75, "urgent": 90}
        percentile = percentiles.get(tx_type, 50)

        # 计算目标优先费用
        target_fee = np.percentile(recent_fees, percentile)

        # 确保在限制范围内
        return min(max(target_fee, self.min_priority_fee), self.max_priority_fee)

    def _get_fallback_gas_price(self, tx_type: str) -> Dict[str, float]:
        """获取备用Gas价格

        Args:
            tx_type: 交易类型

        Returns:
            Dict: Gas价格估算结果
        """
        # 使用历史统计数据
        base_fee = self.fee_stats.get("avg_base_fee", 30)  # Gwei
        multipliers = {"standard": 1.1, "fast": 1.3, "urgent": 1.6}
        fee_multiplier = multipliers.get(tx_type, 1.1)

        return {
            "base_fee": base_fee,
            "max_fee_per_gas": base_fee * fee_multiplier,
            "max_priority_fee_per_gas": self.min_priority_fee,
            "estimated_cost": base_fee * fee_multiplier + self.min_priority_fee,
            "timestamp": datetime.now().isoformat(),
            "source": "fallback",
        }

    async def update_gas_stats(self):
        """更新Gas费用统计数据"""
        try:
            # 获取最近100个区块的Gas数据
            latest = self.w3.eth.block_number
            blocks = []
            for block_num in range(latest - 100, latest):
                block = self.w3.eth.get_block(block_num)
                blocks.append(
                    {
                        "number": block_num,
                        "base_fee": block["baseFeePerGas"] / 1e9,
                        "gas_used_ratio": block["gasUsed"] / block["gasLimit"],
                        "timestamp": datetime.fromtimestamp(block["timestamp"]),
                    }
                )

            # 更新统计数据
            base_fees = [b["base_fee"] for b in blocks]
            gas_ratios = [b["gas_used_ratio"] for b in blocks]

            self.fee_stats.update(
                {
                    "avg_base_fee": np.mean(base_fees),
                    "std_base_fee": np.std(base_fees),
                    "avg_gas_used_ratio": np.mean(gas_ratios),
                    "last_update": datetime.now().isoformat(),
                }
            )

            # 检查是否需要发出告警
            if np.mean(gas_ratios) > 0.8:
                await self._create_alert(
                    "High network congestion detected", AlertLevel.MEDIUM
                )

        except Exception as e:
            await self._create_alert(
                f"Failed to update gas stats: {str(e)}", AlertLevel.HIGH
            )

    async def _create_alert(self, message: str, level: AlertLevel):
        """创建告警

        Args:
            message: 告警信息
            level: 告警级别
        """
        alert = Alert(message=message, level=level, timestamp=datetime.now())
        # TODO: 发送告警通知

    async def optimize_gas_settings(self):
        """优化Gas设置"""
        if not self.gas_price_history:
            return

        # 分析历史数据
        fees = np.array([tx["estimated_cost"] for tx in self.gas_price_history])
        success_rates = np.array([tx["success"] for tx in self.gas_price_history])

        # 找到最优费用倍数
        optimal_multiplier = 1.0
        best_score = 0

        for mult in np.arange(1.0, 2.0, 0.1):
            # 计算在该倍数下的成功率和成本
            would_succeed = fees * mult >= np.median(fees[success_rates == 1])
            success_rate = np.mean(would_succeed)
            avg_cost = np.mean(fees * mult)

            # 计算综合得分 (成功率 - 归一化成本)
            score = success_rate - (avg_cost / np.max(fees))

            if score > best_score:
                best_score = score
                optimal_multiplier = mult

        # 更新配置
        self.base_fee_multiplier = optimal_multiplier

    def get_gas_stats(self) -> Dict[str, Any]:
        """获取Gas统计信息"""
        return {
            "current_stats": self.fee_stats,
            "price_history": self.gas_price_history[-100:],  # 最近100条记录
            "settings": {
                "base_fee_multiplier": self.base_fee_multiplier,
                "max_priority_fee": self.max_priority_fee,
                "min_priority_fee": self.min_priority_fee,
            },
        }

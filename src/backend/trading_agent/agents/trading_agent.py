import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

from tradingbot.shared.sentiment.sentiment_analyzer import analyze_text

from .base_agent import BaseAgent
from .wallet_manager import WalletManager

logger = logging.getLogger(__name__)


class TradingAgent(BaseAgent):
    def __init__(self, name: str, agent_type: str, config: Dict[str, Any]):
        super().__init__(name, agent_type, config)
        self.enabled = config.get("enabled", True)
        self.parameters = config.get("parameters", {})
        self.strategy_type = config.get("strategy_type", "default")
        self.risk_level = config.get("parameters", {}).get("riskLevel", "low")
        self.trade_size = config.get("parameters", {}).get("tradeSize", 1)
        self.wallet = WalletManager()
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-v3")
        self.api_url = "https://api.deepseek.com/v3/completions"
        self.analyze_text = analyze_text

    async def _analyze_market_conditions(self, symbol: str) -> Dict[str, Any]:
        """Analyze market conditions using sentiment analysis."""
        try:
            # Analyze market sentiment from various sources
            market_text = (
                f"Market sentiment for {symbol}"  # TODO: Get real market sentiment text
            )
            sentiment = await self.analyze_text(market_text)

            # Analyze news sentiment
            news_text = f"News about {symbol}"  # TODO: Get real news text
            news = await self.analyze_text(news_text)

            # Analyze social media sentiment
            social_text = (
                f"Social media posts about {symbol}"  # TODO: Get real social media text
            )
            social = await self.analyze_text(social_text)

            return {
                "market_sentiment": sentiment,
                "news_analysis": news,
                "social_analysis": social,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Market analysis failed: {str(e)}")
            return {}

    async def _generate_strategy(
        self, market_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generate trading strategy using DeepSeek R1."""
        # Get market analysis
        symbol = market_data.get("symbol", "").split("/")[
            0
        ]  # Extract base symbol (e.g., "SOL" from "SOL/USDT")
        market_analysis = await self._analyze_market_conditions(symbol)

        prompt = f"""根据以下市场数据和分析生成交易策略：

市场数据：
{json.dumps(market_data, ensure_ascii=False, indent=2)}

市场分析：
{json.dumps(market_analysis, ensure_ascii=False, indent=2)}

交易参数：
- 策略类型：{self.strategy_type}
- 风险等级：{self.risk_level}
- 交易规模：{self.trade_size}

请生成包含以下内容的JSON格式交易策略：
- action: 交易动作（buy/sell/hold）
- price: 目标价格
- size: 交易数量
- stop_loss: 止损价格
- take_profit: 止盈价格
- confidence: 置信度（0-1）
- reasoning: 策略理由
- risk_assessment: 风险评估
- sentiment_impact: 情感分析对策略的影响

请以JSON格式返回策略。"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": 1500,
            "temperature": 0.7,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url, headers=headers, json=data
                ) as response:
                    if response.status != 200:
                        logger.error(f"DeepSeek API error: {response.status}")
                        return None
                    result = await response.json()
                    strategy = json.loads(result["choices"][0]["text"])
                    logger.info(
                        f"Generated strategy for {symbol}: {json.dumps(strategy, ensure_ascii=False)}"
                    )
                    return strategy
        except Exception as e:
            logger.error(f"Strategy generation failed: {str(e)}")
            return None

    async def start(self):
        """Start trading operations"""
        try:
            # Verify wallet balance before starting
            balance = await self.get_wallet_balance()
            if balance < 0.5:  # Minimum 0.5 SOL required
                self.status = "error"
                self.last_update = datetime.now().isoformat()
                return False

            # Generate initial strategy
            market_data = {
                "symbol": self.config.get("symbol", "SOL/USDT"),
                "price": 0.0,  # TODO: Get real-time price
                "volume_24h": 0.0,  # TODO: Get real volume
                "market_cap": 0.0,  # TODO: Get market cap
                "timestamp": datetime.now().isoformat(),
            }

            strategy = await self._generate_strategy(market_data)
            if strategy:
                logger.info(
                    f"Generated strategy: {json.dumps(strategy, ensure_ascii=False)}"
                )

            self.status = "active"
            self.last_update = datetime.now().isoformat()
        except Exception as e:
            self.status = "error"
            self.last_update = datetime.now().isoformat()
            raise Exception(f"Failed to start trading agent: {str(e)}")

    async def stop(self):
        """Stop trading operations"""
        self.status = "inactive"
        self.last_update = datetime.now().isoformat()
        # TODO: 清理交易状态

    async def update_config(self, new_config: Dict[str, Any]):
        """Update trading configuration"""
        self.config = new_config
        self.strategy_type = new_config.get("strategy_type", self.strategy_type)
        self.risk_level = new_config.get("parameters", {}).get(
            "riskLevel", self.risk_level
        )
        self.trade_size = new_config.get("parameters", {}).get(
            "tradeSize", self.trade_size
        )
        self.last_update = datetime.now().isoformat()

    async def get_wallet_balance(self) -> float:
        """Get current wallet balance"""
        try:
            return await self.wallet.get_balance()
        except Exception as e:
            return 0.0

    def validate_parameters(self):
        """Validate trading parameters"""
        if self.parameters.get("max_position_size", 0) <= 0:
            raise ValueError("max_position_size must be positive")
        if self.parameters.get("min_profit_threshold", 0) <= 0:
            raise ValueError("min_profit_threshold must be positive")
        if self.parameters.get("stop_loss_threshold", 0) <= 0:
            raise ValueError("stop_loss_threshold must be positive")
        if self.parameters.get("order_timeout", 0) <= 0:
            raise ValueError("order_timeout must be positive")
        if self.parameters.get("max_slippage", 0) <= 0:
            raise ValueError("max_slippage must be positive")

    def get_status(self) -> Dict[str, Any]:
        """Get detailed trading status"""
        status = super().get_status()
        status.update(
            {
                "strategy_type": self.strategy_type,
                "risk_level": self.risk_level,
                "trade_size": self.trade_size,
                "wallet_address": self.wallet.get_public_key(),
            }
        )
        return status

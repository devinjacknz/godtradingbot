from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional
import asyncio
import logging

from src.shared.models.meme_trading import MemeOpportunity
from src.backend.services.dex.aggregator import DEXAggregator
from src.backend.trading.meme_manager import MemeManager
from src.shared.models.ollama import OllamaModel

logger = logging.getLogger(__name__)

class TradingMode(str, Enum):
    DEX_SWAP = "dex_swap"
    PUMP_FUN = "pump_fun"

class StrategyMetrics:
    def __init__(self):
        self.total_pnl: Decimal = Decimal("0")
        self.win_rate: Decimal = Decimal("0")
        self.avg_return: Decimal = Decimal("0")
        self.volatility: Decimal = Decimal("0")
        self.sharpe_ratio: Decimal = Decimal("0")
        self.max_drawdown: Decimal = Decimal("0")

class StrategySwitcher:
    def __init__(
        self,
        dex_aggregator: DEXAggregator,
        meme_manager: MemeManager,
        ai_model: OllamaModel,
        min_mode_duration: int = 300,  # 5 minutes
        metrics_window: int = 3600,    # 1 hour
    ):
        self.dex_aggregator = dex_aggregator
        self.meme_manager = meme_manager
        self.ai_model = ai_model
        self.current_mode = TradingMode.DEX_SWAP
        self.mode_switch_time = datetime.utcnow()
        self.min_mode_duration = min_mode_duration
        self.metrics_window = metrics_window
        self.mode_metrics: Dict[TradingMode, StrategyMetrics] = {
            TradingMode.DEX_SWAP: StrategyMetrics(),
            TradingMode.PUMP_FUN: StrategyMetrics(),
        }

    async def evaluate_market_conditions(self) -> Dict[str, Decimal]:
        dex_opportunities = await self.dex_aggregator.scan_opportunities(
            min_liquidity=Decimal("10000"),
            max_spread=Decimal("0.01")
        )
        
        meme_opportunities = await self.meme_manager.scan_opportunities(
            min_market_cap=Decimal("100000"),
            min_volume=Decimal("50000")
        )

        # Get AI analysis of market conditions
        market_analysis = await self.ai_model.analyze_market_conditions(
            dex_opportunities=dex_opportunities,
            meme_opportunities=meme_opportunities
        )

        return {
            "dex_score": Decimal(str(market_analysis.get("dex_score", 0))),
            "meme_score": Decimal(str(market_analysis.get("meme_score", 0))),
            "market_volatility": Decimal(str(market_analysis.get("volatility", 0))),
            "trend_strength": Decimal(str(market_analysis.get("trend_strength", 0)))
        }

    async def should_switch_mode(self) -> Optional[TradingMode]:
        # Check minimum duration
        if (datetime.utcnow() - self.mode_switch_time).total_seconds() < self.min_mode_duration:
            return None

        # Analyze current market conditions
        market_conditions = await self.evaluate_market_conditions()
        
        # Get strategy performance metrics
        dex_metrics = self.mode_metrics[TradingMode.DEX_SWAP]
        meme_metrics = self.mode_metrics[TradingMode.PUMP_FUN]

        # Analyze optimal strategy using AI
        strategy_analysis = await self.ai_model.analyze_strategy_switch(
            current_mode=self.current_mode,
            market_conditions=market_conditions,
            dex_metrics=vars(dex_metrics),
            meme_metrics=vars(meme_metrics)
        )

        recommended_mode = strategy_analysis.get("recommended_mode")
        switch_confidence = Decimal(str(strategy_analysis.get("confidence", 0)))

        if switch_confidence > Decimal("0.8") and recommended_mode != self.current_mode:
            logger.info(f"Strategy switch recommended: {recommended_mode} (confidence: {switch_confidence})")
            return TradingMode(recommended_mode)

        return None

    async def update_metrics(self, mode: TradingMode, trade_result: Dict) -> None:
        metrics = self.mode_metrics[mode]
        
        # Update strategy metrics based on trade result
        pnl = Decimal(str(trade_result.get("pnl", 0)))
        metrics.total_pnl += pnl
        
        # Update other metrics (win rate, volatility, etc.)
        if pnl > 0:
            metrics.win_rate = (metrics.win_rate * 9 + Decimal("1")) / Decimal("10")
        else:
            metrics.win_rate = metrics.win_rate * 9 / Decimal("10")

        # Calculate rolling metrics
        metrics.avg_return = (metrics.avg_return * 9 + pnl) / Decimal("10")
        metrics.volatility = Decimal(str(trade_result.get("volatility", metrics.volatility)))
        metrics.sharpe_ratio = Decimal(str(trade_result.get("sharpe_ratio", metrics.sharpe_ratio)))
        metrics.max_drawdown = max(metrics.max_drawdown, Decimal(str(trade_result.get("drawdown", 0))))

    async def run(self) -> None:
        while True:
            try:
                new_mode = await self.should_switch_mode()
                if new_mode and new_mode != self.current_mode:
                    logger.info(f"Switching trading mode from {self.current_mode} to {new_mode}")
                    self.current_mode = new_mode
                    self.mode_switch_time = datetime.utcnow()

                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in strategy switcher: {str(e)}")
                await asyncio.sleep(5)  # Brief pause on error

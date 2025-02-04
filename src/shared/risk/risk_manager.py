import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from src.shared.models.cache import CacheConfig, MarketDataCache, RateLimitCache
from src.shared.models.database import delete_cache, get_cache, set_cache

logger = logging.getLogger(__name__)

from dataclasses import dataclass, field
from typing import List


@dataclass
class RiskConfig:
    MIN_CONFIDENCE: float = 0.7
    RISK_PER_TRADE: float = 0.02
    MAX_DRAWDOWN: float = 0.1
    MAX_POSITION_SIZE: float = 10000
    MAX_LEVERAGE: float = 10
    MAX_MEME_RISK: float = 0.7
    MIN_LIQUIDITY: float = 100000
    MAX_SLIPPAGE: float = 0.02
    STOP_LOSS_MULTIPLIER: float = 2.0
    TAKE_PROFIT_MULTIPLIER: float = 3.0
    VOLATILITY_SCALE_THRESHOLD: float = 1.5
    POSITION_REDUCTION_RATE: float = 0.7
    TRAILING_STOP_ACTIVATION: float = 1.5
    DYNAMIC_TAKE_PROFIT_LEVELS: List[float] = field(
        default_factory=lambda: [0.33, 0.5, 1.0]
    )
    MEME_MAX_ALLOCATION: float = 0.05
    MEME_VOLATILITY_CUSHION: float = 0.02
    MEME_MAX_POSITION_SIZE: float = 5000
    MEME_MIN_LIQUIDITY: float = 50000
    MEME_MAX_SLIPPAGE: float = 0.05
    MEME_STOP_LOSS_MULTIPLIER: float = 1.5
    MEME_TAKE_PROFIT_MULTIPLIER: float = 4.0

    def validate(self):
        if not 0 < self.MIN_CONFIDENCE <= 1:
            raise ValueError("MIN_CONFIDENCE must be between 0 and 1")
        if not 0 < self.RISK_PER_TRADE <= 0.1:
            raise ValueError("RISK_PER_TRADE must be between 0 and 0.1 (10%)")
        if not 0 < self.MAX_DRAWDOWN <= 0.2:
            raise ValueError("MAX_DRAWDOWN must be between 0 and 0.2 (20%)")
        if self.MAX_POSITION_SIZE <= 0:
            raise ValueError("MAX_POSITION_SIZE must be positive")
        if not 1 <= self.MAX_LEVERAGE <= 20:
            raise ValueError("MAX_LEVERAGE must be between 1 and 20")
        if not 0 < self.MAX_MEME_RISK <= 1:
            raise ValueError("MAX_MEME_RISK must be between 0 and 1")
        if self.MIN_LIQUIDITY <= 0:
            raise ValueError("MIN_LIQUIDITY must be positive")
        if not 0 < self.MAX_SLIPPAGE <= 0.05:
            raise ValueError("MAX_SLIPPAGE must be between 0 and 0.05 (5%)")
        if not 0 < self.STOP_LOSS_MULTIPLIER <= 5:
            raise ValueError("STOP_LOSS_MULTIPLIER must be between 0 and 5")
        if not 0 < self.TAKE_PROFIT_MULTIPLIER <= 10:
            raise ValueError("TAKE_PROFIT_MULTIPLIER must be between 0 and 10")
        if not 0 < self.VOLATILITY_SCALE_THRESHOLD <= 3:
            raise ValueError("VOLATILITY_SCALE_THRESHOLD must be between 0 and 3")
        if not 0 < self.POSITION_REDUCTION_RATE <= 1:
            raise ValueError("POSITION_REDUCTION_RATE must be between 0 and 1")
        if not 0 < self.TRAILING_STOP_ACTIVATION <= 3:
            raise ValueError("TRAILING_STOP_ACTIVATION must be between 0 and 3")
        if not self.DYNAMIC_TAKE_PROFIT_LEVELS:
            raise ValueError("DYNAMIC_TAKE_PROFIT_LEVELS cannot be empty")
        if not all(0 < x <= 2 for x in self.DYNAMIC_TAKE_PROFIT_LEVELS):
            raise ValueError(
                "DYNAMIC_TAKE_PROFIT_LEVELS values must be between 0 and 2 (200%)"
            )
        if not all(
            self.DYNAMIC_TAKE_PROFIT_LEVELS[i] < self.DYNAMIC_TAKE_PROFIT_LEVELS[i + 1]
            for i in range(len(self.DYNAMIC_TAKE_PROFIT_LEVELS) - 1)
        ):
            raise ValueError("DYNAMIC_TAKE_PROFIT_LEVELS must be in ascending order")

        # Validate meme coin parameters
        if not 0 < self.MEME_MAX_ALLOCATION <= 0.1:
            raise ValueError("MEME_MAX_ALLOCATION must be between 0 and 0.1 (10%)")
        if not 0 < self.MEME_VOLATILITY_CUSHION <= 0.05:
            raise ValueError("MEME_VOLATILITY_CUSHION must be between 0 and 0.05 (5%)")
        if not 0 < self.MEME_MAX_POSITION_SIZE <= self.MAX_POSITION_SIZE:
            raise ValueError(
                "MEME_MAX_POSITION_SIZE must be between 0 and MAX_POSITION_SIZE"
            )
        if not 0 < self.MEME_MIN_LIQUIDITY <= self.MIN_LIQUIDITY:
            raise ValueError("MEME_MIN_LIQUIDITY must be between 0 and MIN_LIQUIDITY")
        if not 0 < self.MEME_MAX_SLIPPAGE <= 0.1:
            raise ValueError("MEME_MAX_SLIPPAGE must be between 0 and 0.1 (10%)")
        if not 0 < self.MEME_STOP_LOSS_MULTIPLIER <= 3:
            raise ValueError("MEME_STOP_LOSS_MULTIPLIER must be between 0 and 3")
        if not 0 < self.MEME_TAKE_PROFIT_MULTIPLIER <= 5:
            raise ValueError("MEME_TAKE_PROFIT_MULTIPLIER must be between 0 and 5")


class RiskAssessment(BaseModel):
    is_valid: bool
    confidence: float
    risk_level: float
    max_loss: float
    position_size: float
    volatility_exposure: float
    expected_return: float
    risk_reward_ratio: float
    market_conditions_alignment: float
    recommendations: List[str]
    reason: str
    take_profit_levels: Optional[List[float]] = None
    trailing_stop_level: Optional[float] = None
    dynamic_position_size: Optional[float] = None
    market_impact: float = 0.0
    slippage: float = 0.0
    expected_slippage: float = 0.0
    margin_requirements: Dict[str, float] = {"required": 0.0, "available": 0.0}
    correlation_factor: float = 0.0
    liquidity_score: float = 0.0
    volume_profile: Dict[str, Any] = {}
    market_data_source: str = "live"
    is_stale: bool = False
    rate_limit_info: Dict[str, Any] = {
        "is_limited": False,
        "remaining": 100,
        "reset": 0.0,
    }

    def get(self, key: str, default: Any = None) -> Any:
        """Provide dict-like .get() method for compatibility"""
        try:
            return getattr(self, key, default)
        except AttributeError:
            return default

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access to attributes"""
        return getattr(self, key)


class RiskManager:
    """Risk management system."""

    async def adjust_for_meme_coins(
        self, risk_params: Dict[str, Any], token_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Adjust risk parameters for meme coins."""
        if token_info.get("is_meme", False):
            risk_params.update(
                {
                    "max_allocation": self.config.MEME_MAX_ALLOCATION,
                    "max_position_size": self.config.MEME_MAX_POSITION_SIZE,
                    "min_liquidity": self.config.MEME_MIN_LIQUIDITY,
                    "max_slippage": self.config.MEME_MAX_SLIPPAGE,
                    "stop_loss_multiplier": self.config.MEME_STOP_LOSS_MULTIPLIER,
                    "take_profit_multiplier": self.config.MEME_TAKE_PROFIT_MULTIPLIER,
                    "volatility_cushion": self.config.MEME_VOLATILITY_CUSHION,
                }
            )

            # Apply volatility cushion to position sizing
            if "position_size" in risk_params:
                risk_params["position_size"] *= (
                    1.0 - self.config.MEME_VOLATILITY_CUSHION
                )

            # Adjust take profit levels for higher volatility
            if "take_profit_levels" in risk_params:
                risk_params["take_profit_levels"] = [
                    level * self.config.MEME_TAKE_PROFIT_MULTIPLIER
                    for level in risk_params["take_profit_levels"]
                ]

            # Tighten stop loss for meme coins
            if "stop_loss" in risk_params:
                risk_params["stop_loss"] *= self.config.MEME_STOP_LOSS_MULTIPLIER

        return risk_params

    def __init__(self):
        self.config = RiskConfig()
        self.config.validate()
        self._trade_history: List[Dict[str, Any]] = []
        self._position_cache: Dict[str, Dict[str, Any]] = {}
        self._rate_limit_cache: Dict[str, Dict[str, Any]] = {}
        self._market_data_cache: Dict[str, Dict[str, Any]] = {}
        self._last_request_time: Dict[str, float] = {}
        self._request_count: Dict[str, int] = {}
        self._recommendations: List[str] = []
        self._metrics: Dict[str, Any] = {}
        self._current_time = time.time()

    def _add_recommendation(self, recommendation: str) -> None:
        """Add a unique recommendation."""
        if recommendation not in self._recommendations:
            self._recommendations.append(recommendation)

    async def _check_rate_limit(
        self, key: str, max_requests: int = 10, window: float = 60.0
    ) -> Dict[str, Any]:
        current_time = time.time()
        cache_key = f"ratelimit:{key}"

        try:
            cached_data = self._rate_limit_cache.get(cache_key, {})
            requests = cached_data.get("requests", [])
            requests = [ts for ts in requests if current_time - ts < window]
            requests.append(current_time)

            is_limited = len(requests) > max_requests
            remaining = max(0, max_requests - len(requests))
            reset_time = min(requests) + window if requests else current_time + window

            self._rate_limit_cache[cache_key] = {
                "requests": requests[-max_requests:],
                "window_start": current_time,
                "limit": max_requests,
                "window_size": window,
            }

            if is_limited:
                logger.warning(f"Rate limit exceeded for {key}")
                self._add_recommendation(
                    f"Rate limit exceeded for {key} - wait {reset_time - current_time:.1f}s"
                )
                return {
                    "limit": max_requests,
                    "remaining": 0,
                    "reset": reset_time,
                    "is_limited": True,
                    "window_size": window,
                }

            return {
                "limit": max_requests,
                "remaining": remaining,
                "reset": reset_time,
                "is_limited": False,
                "window_size": window,
            }

        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            return {
                "limit": max_requests,
                "remaining": max_requests,
                "reset": current_time + window,
                "is_limited": False,
                "window_size": window,
                "error": str(e),
            }

    @asynccontextmanager
    async def _risk_assessment_timeout(self, timeout: float = 5.0):
        try:
            task = asyncio.create_task(asyncio.sleep(timeout))
            try:
                yield
            finally:
                task.cancel()
        except asyncio.TimeoutError:
            logger.error("Risk assessment timed out")
            raise
        except Exception as e:
            logger.error(f"Risk assessment error: {str(e)}")
            raise

    async def assess_trade(self, trade_params: Dict[str, Any]) -> RiskAssessment:
        logger.info(f"Assessing trade: {json.dumps(trade_params, default=str)}")
        try:
            symbol = trade_params.get("symbol", "BTC/USD")
            current_time = time.time()

            # Basic validation first
            basic_validation = await self._validate_basic_params(trade_params)
            if not basic_validation.is_valid:
                return basic_validation

            # Rate limiting
            rate_limit = await self._check_rate_limit(symbol)
            if rate_limit.get("is_limited", False):
                return RiskAssessment(
                    is_valid=False,
                    confidence=0.95,
                    risk_level=1.0,
                    max_loss=0.0,
                    position_size=0.0,
                    volatility_exposure=1.0,
                    expected_return=0.0,
                    risk_reward_ratio=0.0,
                    market_conditions_alignment=0.0,
                    recommendations=["Rate limit exceeded - please wait"],
                    reason="Rate limit exceeded",
                    take_profit_levels=None,
                    trailing_stop_level=None,
                    dynamic_position_size=None,
                    rate_limit_info=rate_limit,
                )

            # Market data caching with strict validation
            if symbol:
                cache_key = f"market_data:{symbol}"
                cached_data = await get_cache(cache_key)
                current_time = time.time()

                if cached_data:
                    try:
                        cached = json.loads(cached_data)
                        if (
                            current_time - cached["timestamp"] < 300
                        ):  # 5 minute staleness check
                            self._metrics = cached
                            self._metrics["source"] = "cache"
                            self._metrics["is_stale"] = False
                        else:
                            await delete_cache(cache_key)
                            raise ValueError("Cached data too old")
                    except Exception:
                        self._metrics = {}

                if not self._metrics:
                    self._metrics = {
                        "price": float(trade_params.get("price", 0.0)),
                        "volume": float(trade_params.get("volume", 0.0)),
                        "liquidity": float(trade_params.get("liquidity", 0.0)),
                        "spread": float(trade_params.get("spread", 0.0)),
                        "volatility": float(trade_params.get("volatility", 1.0)),
                        "market_impact": float(trade_params.get("market_impact", 0.0)),
                        "slippage": float(trade_params.get("slippage", 0.0)),
                        "bid": float(trade_params.get("bid", 0.0)),
                        "ask": float(trade_params.get("ask", 0.0)),
                        "timestamp": current_time,
                        "symbol": symbol,
                        "source": "live",
                        "is_stale": False,
                    }

                    # Validate required fields
                    required_fields = ["price", "volume", "liquidity"]
                    if any(self._metrics[f] <= 0 for f in required_fields):
                        return RiskAssessment(
                            is_valid=False,
                            confidence=0.95,
                            risk_level=0.9,
                            max_loss=0.0,
                            position_size=0.0,
                            volatility_exposure=1.0,
                            expected_return=0.0,
                            risk_reward_ratio=0.0,
                            market_conditions_alignment=0.0,
                            recommendations=[
                                "Invalid market data parameters",
                                "Check price, volume, and liquidity values",
                            ],
                            reason="Invalid market data",
                            take_profit_levels=None,
                            trailing_stop_level=None,
                            dynamic_position_size=None,
                        )

                    try:
                        await set_cache(
                            cache_key, json.dumps(self._metrics), expire=300
                        )
                    except Exception as e:
                        logger.error(f"Error caching market data: {e}")

            async with self._risk_assessment_timeout():
                basic_validation = await self._validate_basic_params(trade_params)
                if not basic_validation.is_valid:
                    logger.warning(
                        "Trade validation failed", extra={"params": trade_params}
                    )
                    return basic_validation

                position_size = await self._calculate_position_size(trade_params)
                if position_size <= 0:
                    return RiskAssessment(
                        is_valid=False,
                        confidence=0.95,
                        risk_level=0.9,
                        max_loss=0.0,
                        position_size=0.0,
                        volatility_exposure=float(trade_params.get("volatility", 1.0)),
                        expected_return=0.0,
                        risk_reward_ratio=0.0,
                        market_conditions_alignment=0.0,
                        recommendations=[
                            "Invalid position size",
                            "Check account balance and leverage settings",
                        ],
                        reason="Position size calculation failed - insufficient balance or invalid leverage",
                        take_profit_levels=None,
                        trailing_stop_level=None,
                        dynamic_position_size=None,
                        market_impact=0.0,
                        slippage=float(trade_params.get("spread", 0.001)),
                        expected_slippage=float(trade_params.get("spread", 0.001))
                        * 1.5,
                        margin_requirements={"required": 0.0, "available": 0.0},
                        correlation_factor=0.0,
                        liquidity_score=float(trade_params.get("liquidity", 0.0)),
                        volume_profile={
                            "volume": float(trade_params.get("volume", 0.0))
                        },
                        market_data_source="live",
                        is_stale=False,
                        rate_limit_info={
                            "is_limited": False,
                            "remaining": 100,
                            "reset": 0.0,
                        },
                    )

            market_check = await self._check_market_conditions(trade_params)
            if not market_check["is_valid"]:
                return RiskAssessment(
                    is_valid=False,
                    confidence=0.9,
                    risk_level=0.8,
                    max_loss=float(trade_params.get("max_loss", 1000.0)),
                    position_size=float(trade_params.get("position_size", 0.0)),
                    volatility_exposure=float(trade_params.get("volatility", 1.0)),
                    expected_return=float(trade_params.get("expected_return", 0.0)),
                    risk_reward_ratio=float(trade_params.get("risk_reward", 0.0)),
                    market_conditions_alignment=0.2,
                    recommendations=market_check.get(
                        "recommendations", ["Poor market conditions"]
                    ),
                    reason=market_check["reason"],
                    take_profit_levels=None,
                    trailing_stop_level=None,
                    dynamic_position_size=None,
                    market_impact=market_check.get("market_impact", 0.0),
                    expected_slippage=market_check.get("expected_slippage", 0.0),
                    market_data_source=market_check.get("market_data", {}).get(
                        "source", "live"
                    ),
                    is_stale=market_check.get("is_stale", False),
                )

            metrics_dict = await self._calculate_risk_metrics(
                trade_params, position_size
            )
            initial_assessment = RiskAssessment(
                is_valid=True,
                confidence=0.85,
                risk_level=metrics_dict.get("risk_level", 0.5),
                max_loss=metrics_dict.get("max_loss", 0.0),
                position_size=metrics_dict.get("position_size", 0.0),
                volatility_exposure=trade_params.get("volatility", 1.0),
                expected_return=metrics_dict.get("expected_return", 0.0),
                risk_reward_ratio=metrics_dict.get("risk_reward", 0.0),
                market_conditions_alignment=1.0,
                recommendations=[],
                reason="Initial assessment",
                take_profit_levels=metrics_dict.get("take_profit_levels"),
                trailing_stop_level=metrics_dict.get("trailing_stop"),
                dynamic_position_size=metrics_dict.get(
                    "adjusted_position", position_size
                ),
                market_impact=metrics_dict.get("market_impact", 0.0),
                slippage=metrics_dict.get("expected_slippage", 0.0),
                expected_slippage=metrics_dict.get("expected_slippage", 0.0),
                margin_requirements=metrics_dict.get(
                    "margin_requirements", {"required": 0.0, "available": 0.0}
                ),
                correlation_factor=metrics_dict.get("correlation", 0.0),
                liquidity_score=metrics_dict.get("liquidity", 0.0),
                volume_profile={"volume": metrics_dict.get("volume", 0.0)},
            )

            validation_result = await self._validate_risk_metrics(initial_assessment)
            if not validation_result.is_valid:
                return validation_result

            # Generate final recommendations
            recommendations = await self._generate_recommendations(initial_assessment)

            # Update recommendations and return
            initial_assessment.recommendations = recommendations
            initial_assessment.reason = "Trade meets risk criteria"
            return initial_assessment

        except Exception as e:
            return RiskAssessment(
                is_valid=False,
                confidence=0.95,
                risk_level=1.0,
                max_loss=0.0,
                position_size=0.0,
                volatility_exposure=1.0,
                expected_return=0.0,
                risk_reward_ratio=0.0,
                market_conditions_alignment=0.0,
                recommendations=["System error occurred"],
                reason=f"Error in risk assessment: {str(e)}",
                take_profit_levels=None,
                trailing_stop_level=None,
                dynamic_position_size=None,
            )

    async def _validate_basic_params(self, params: Dict[str, Any]) -> RiskAssessment:
        """Validate basic trade parameters."""
        try:
            # Required parameters
            try:
                amount = float(params.get("amount", 1.0))
                price = float(params.get("price", 50000.0))
                leverage = float(params.get("leverage", 1.0))
                volatility = float(params.get("volatility", 1.0))
                liquidity = float(params.get("liquidity", self.config.MIN_LIQUIDITY))
                volume = float(params.get("volume", liquidity * 0.1))
                spread = float(params.get("spread", 0.001))
            except (ValueError, TypeError):
                return RiskAssessment(
                    is_valid=False,
                    confidence=0.95,
                    risk_level=1.0,
                    max_loss=0.0,
                    position_size=0.0,
                    volatility_exposure=1.0,
                    expected_return=0.0,
                    risk_reward_ratio=0.0,
                    market_conditions_alignment=0.0,
                    recommendations=[
                        "Invalid trade parameters",
                        "Amount and price must be numeric",
                    ],
                    reason="Invalid trade parameters: numeric conversion failed",
                    take_profit_levels=None,
                    trailing_stop_level=None,
                    dynamic_position_size=None,
                    market_impact=0.0,
                    slippage=0.0,
                    expected_slippage=0.0,
                    margin_requirements={"required": 0.0, "available": 0.0},
                    correlation_factor=0.0,
                    liquidity_score=0.0,
                    volume_profile={},
                    market_data_source="live",
                    is_stale=False,
                    rate_limit_info={
                        "is_limited": False,
                        "remaining": 100,
                        "reset": 0.0,
                    },
                )

            # Validate parameters
            if amount <= 0 or price <= 0:
                return RiskAssessment(
                    is_valid=False,
                    confidence=0.95,
                    risk_level=0.9,
                    max_loss=0.0,
                    position_size=0.0,
                    volatility_exposure=volatility,
                    expected_return=0.0,
                    risk_reward_ratio=0.0,
                    market_conditions_alignment=0.2,
                    recommendations=[
                        "Invalid trade parameters",
                        "Amount and price must be positive",
                    ],
                    reason="Invalid trade parameters: negative or zero amount/price",
                    take_profit_levels=None,
                    trailing_stop_level=None,
                    dynamic_position_size=None,
                    market_impact=0.0,
                    slippage=spread,
                    expected_slippage=spread * 1.5,
                    margin_requirements={"required": 0.0, "available": 0.0},
                    correlation_factor=0.0,
                    liquidity_score=liquidity,
                    volume_profile={"volume": volume, "liquidity": liquidity},
                    market_data_source="live",
                    is_stale=False,
                    rate_limit_info={
                        "is_limited": False,
                        "remaining": 100,
                        "reset": 0.0,
                    },
                )

            if leverage > self.config.MAX_LEVERAGE:
                return RiskAssessment(
                    is_valid=False,
                    confidence=0.95,
                    risk_level=1.0,
                    max_loss=0.0,
                    position_size=0.0,
                    volatility_exposure=volatility,
                    expected_return=0.0,
                    risk_reward_ratio=0.0,
                    market_conditions_alignment=0.0,
                    recommendations=["Invalid trade parameters"],
                    reason="Invalid trade parameters: leverage too high",
                    take_profit_levels=None,
                    trailing_stop_level=None,
                    dynamic_position_size=None,
                    market_impact=0.0,
                    slippage=0.0,
                    expected_slippage=0.0,
                    margin_requirements={"required": 0.0, "available": 0.0},
                    correlation_factor=0.0,
                    liquidity_score=0.0,
                    volume_profile={},
                    market_data_source="live",
                    is_stale=False,
                    rate_limit_info={
                        "is_limited": False,
                        "remaining": 100,
                        "reset": 0.0,
                    },
                )

            return RiskAssessment(
                is_valid=True,
                confidence=0.95,
                risk_level=0.5,
                max_loss=amount * price * 0.02,
                position_size=amount,
                volatility_exposure=volatility,
                expected_return=amount * price * 0.03,
                risk_reward_ratio=1.5,
                market_conditions_alignment=0.8,
                recommendations=["Basic parameters validated"],
                reason="Basic validation passed",
                take_profit_levels=[price * 1.01, price * 1.02, price * 1.03],
                trailing_stop_level=price * 0.98,
                dynamic_position_size=amount,
                market_impact=0.0001,
                slippage=spread,
                expected_slippage=spread * 1.5,
                margin_requirements={
                    "required": amount * price * 0.1,
                    "available": float("inf"),
                },
                correlation_factor=0.0,
                liquidity_score=liquidity,
                volume_profile={"volume": volume, "liquidity": liquidity},
                market_data_source="live",
                is_stale=False,
                rate_limit_info={"is_limited": False, "remaining": 100, "reset": 0.0},
            )
            params["market_impact"] = float(params.get("market_impact", 0.0001))
            params["slippage"] = float(params.get("slippage", 0.0001))
            params["is_meme_coin"] = bool(params.get("is_meme_coin", False))

            # Validate values
            if params["amount"] <= 0:
                return False, "Invalid trade parameters: amount must be positive"
            if params["price"] <= 0:
                return False, "Invalid trade parameters: price must be positive"
            if params["leverage"] > self.config.MAX_LEVERAGE * (
                2.0 if params["is_meme_coin"] else 1.5
            ):
                return False, "Invalid trade parameters: leverage too high"
            if params["volatility"] <= 0:
                return False, "Invalid trade parameters: volatility must be positive"
            if params["liquidity"] < 0:
                return False, "Invalid trade parameters: liquidity cannot be negative"
            if params["volume"] < 0:
                return False, "Invalid trade parameters: volume cannot be negative"

            # Ensure positive values for market data
            params["volatility"] = max(0.1, params["volatility"])
            params["liquidity"] = max(
                self.config.MIN_LIQUIDITY * 0.1, params["liquidity"]
            )
            params["volume"] = max(params["liquidity"] * 0.01, params["volume"])
            params["spread"] = max(0.0001, min(0.1, params["spread"]))

            return RiskAssessment(
                is_valid=True,
                confidence=0.95,
                risk_level=0.1,
                max_loss=0.0,
                position_size=float(params.get("amount", 0.0)),
                volatility_exposure=float(params.get("volatility", 1.0)),
                expected_return=0.0,
                risk_reward_ratio=0.0,
                market_conditions_alignment=1.0,
                recommendations=["Parameters valid"],
                reason="Valid parameters",
            )
        except Exception as e:
            logger.error(f"Parameter validation error: {e}")
            return RiskAssessment(
                is_valid=False,
                confidence=0.95,
                risk_level=1.0,
                max_loss=0.0,
                position_size=0.0,
                volatility_exposure=1.0,
                expected_return=0.0,
                risk_reward_ratio=0.0,
                market_conditions_alignment=0.0,
                recommendations=["Invalid parameters"],
                reason=f"Invalid trade parameters: {str(e)}",
            )

    async def _calculate_position_size(self, params: Dict[str, Any]) -> float:
        try:
            account_size = float(params.get("account_size", 100000))
            amount = float(params.get("amount", 0))
            volatility = float(params.get("volatility", 1.0))
            liquidity = float(params.get("liquidity", 0))
            spread = float(params.get("spread", 0.001))
            price = float(params.get("price", 0))

            if amount <= 0 or price <= 0:
                return 0

            base_size = amount
            position_value = base_size * price

            # Portfolio risk checks
            existing_positions = params.get("existing_positions", [])
            total_exposure = sum(
                float(pos.get("amount", 0)) * float(pos.get("price", 0))
                for pos in existing_positions
            )

            # Margin utilization check
            margin_used = sum(
                float(pos.get("margin_used", 0)) for pos in existing_positions
            )
            margin_ratio = (
                margin_used / account_size if account_size > 0 else float("inf")
            )
            if margin_ratio > 0.7:
                base_size *= 0.6

            # Drawdown check
            unrealized_pnl = sum(
                float(pos.get("unrealized_pnl", 0)) for pos in existing_positions
            )
            if unrealized_pnl < -account_size * 0.05:
                base_size *= 0.8

            # Correlation check
            correlation = await self._is_correlated(params)
            if correlation > 0.7:
                base_size *= 1.0 - correlation * 0.5

            # Market condition adjustments
            if volatility > self.config.VOLATILITY_SCALE_THRESHOLD:
                vol_reduction = max(
                    0.3,
                    1.0 - (volatility - self.config.VOLATILITY_SCALE_THRESHOLD) / 2.0,
                )
                base_size *= vol_reduction

            if liquidity < self.config.MIN_LIQUIDITY:
                liq_factor = max(0.3, liquidity / self.config.MIN_LIQUIDITY)
                base_size *= liq_factor

            if spread > self.config.MAX_SLIPPAGE * 0.5:
                spread_factor = max(0.3, 1.0 - (spread / self.config.MAX_SLIPPAGE))
                base_size *= spread_factor

            # Portfolio concentration limit
            max_position = account_size * self.config.RISK_PER_TRADE
            if params.get("is_meme_coin", False):
                max_position *= 0.5

            # Final position size with limits
            return min(base_size, max_position)

        except (ValueError, TypeError, ZeroDivisionError) as e:
            logger.error(f"Error calculating position size: {str(e)}")
            return 0

    def _to_timestamp(self, value) -> float:
        """Convert various time formats to Unix timestamp."""
        if isinstance(value, datetime):
            return value.timestamp()
        elif isinstance(value, str):
            try:
                return datetime.fromisoformat(value).timestamp()
            except ValueError:
                return float(value)
        return float(value or 0)

    async def _check_market_conditions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate current market conditions with lenient thresholds."""
        symbol = str(params["symbol"])
        current_time = time.time()
        is_meme = bool(params.get("is_meme_coin", False))

        market_data = {
            "price": float(params["price"]),
            "volume": float(params["volume"]),
            "liquidity": float(params["liquidity"]),
            "spread": float(params["spread"]),
            "volatility": float(params["volatility"]),
            "timestamp": current_time,
            "source": "live",
            "is_meme": is_meme,
        }

        if market_data["price"] <= 0:
            return {
                "is_valid": False,
                "reason": "Invalid price data - trade rejected",
                "recommendations": [
                    "Price data must be positive",
                    "Verify data source connectivity",
                    "Check market status",
                ],
                "market_data": market_data,
                "market_impact": 0.0,
                "expected_slippage": 0.0,
                "market_conditions_alignment": 0.0,
            }

        amount = float(params["amount"])
        position_value = amount * market_data["price"]

        # Stricter market impact calculation
        base_impact = (
            (position_value / market_data["liquidity"])
            if market_data["liquidity"] > 0
            else float("inf")
        )
        volume_scale = (
            min(0.5, market_data["volume"] / (position_value * 1000))
            if position_value > 0
            else 0.1
        )
        volatility_scale = min(1.2, 1.0 + market_data["volatility"] * 0.05)
        market_impact = round(base_impact * volume_scale * volatility_scale * 0.2, 6)

        # Reject trade if market impact is too high
        if market_impact > self.config.MAX_SLIPPAGE * 0.5:
            return {
                "is_valid": False,
                "reason": "Excessive market impact - trade rejected",
                "recommendations": [
                    f"Market impact ({market_impact:.4f}) exceeds threshold ({self.config.MAX_SLIPPAGE * 0.5:.4f})",
                    "Consider reducing position size",
                    "Wait for higher liquidity",
                ],
                "market_data": market_data,
                "market_impact": market_impact,
                "expected_slippage": 0.0,
                "market_conditions_alignment": 0.1,
            }

        # Ultra-strict slippage calculation with comprehensive factors
        base_slippage = market_impact + (
            market_data["spread"] * 0.25
        )  # Higher spread impact
        volume_factor = (
            max(0.6, min(1.1, market_data["volume"] / (position_value * 100)))
            if position_value > 0
            else 0.6
        )
        volatility_impact = max(1.0, market_data["volatility"] * 0.1)
        expected_slippage = round(base_slippage * volatility_impact / volume_factor, 6)

        if is_meme:
            expected_slippage *= 2.5  # Even higher penalty for meme coins
            market_impact *= 2.0

        # Reject trade if expected slippage is too high
        if (
            expected_slippage > self.config.MAX_SLIPPAGE * 0.6
        ):  # Stricter slippage threshold
            return {
                "is_valid": False,
                "reason": "Excessive expected slippage - trade rejected",
                "recommendations": [
                    f"Expected slippage ({expected_slippage:.4f}) exceeds threshold ({self.config.MAX_SLIPPAGE * 0.6:.4f})",
                    "Consider reducing position size",
                    "Wait for better market conditions",
                    f"Current spread: {market_data['spread']:.4f}",
                    f"Market impact: {market_impact:.4f}",
                ],
                "market_data": market_data,
                "market_impact": market_impact,
                "expected_slippage": expected_slippage,
                "market_conditions_alignment": 0.1,
            }

        market_conditions = []
        position_scale = 1.0

        max_volatility = 2.5 if is_meme else 1.8  # Stricter volatility limits
        if market_data["volatility"] > max_volatility:
            if (
                market_data["volatility"] > max_volatility * 1.5
            ):  # Reject extremely volatile conditions
                return {
                    "is_valid": False,
                    "reason": "Extreme volatility - trade rejected",
                    "recommendations": [
                        f"Current volatility ({market_data['volatility']:.2f}) exceeds maximum ({max_volatility * 1.5:.2f})",
                        "Wait for market stabilization",
                        "Consider alternative trading pairs",
                    ],
                    "market_data": market_data,
                    "market_impact": market_impact,
                    "expected_slippage": expected_slippage,
                    "market_conditions_alignment": 0.1,
                }
            vol_scale = max(
                0.3, 1.0 - (market_data["volatility"] - max_volatility) / max_volatility
            )
            position_scale *= vol_scale
            market_conditions.append(
                {
                    "condition": "volatility",
                    "status": "warning",
                    "message": f"High volatility - position scaled to {vol_scale:.0%}",
                    "scale": vol_scale,
                }
            )

        min_liquidity = self.config.MIN_LIQUIDITY * (
            0.4 if is_meme else 0.8
        )  # Higher liquidity requirements
        if market_data["liquidity"] < min_liquidity:
            if (
                market_data["liquidity"] < min_liquidity * 0.5
            ):  # Reject extremely low liquidity
                return {
                    "is_valid": False,
                    "reason": "Insufficient liquidity - trade rejected",
                    "recommendations": [
                        f"Current liquidity ({market_data['liquidity']:.0f}) below minimum ({min_liquidity * 0.5:.0f})",
                        "Wait for higher market liquidity",
                        "Consider major trading pairs",
                    ],
                    "market_data": market_data,
                    "market_impact": market_impact,
                    "expected_slippage": expected_slippage,
                    "market_conditions_alignment": 0.1,
                }
            liq_scale = max(0.3, market_data["liquidity"] / min_liquidity)
            position_scale *= liq_scale
            market_conditions.append(
                {
                    "condition": "liquidity",
                    "status": "warning",
                    "message": f"Low liquidity - position scaled to {liq_scale:.0%}",
                    "scale": liq_scale,
                }
            )

        position_value = float(params["amount"]) * market_data["price"]
        base_min_volume = position_value * 5  # Higher base volume requirement
        volatility_factor = max(
            0.7, market_data["volatility"] / 2.0
        )  # Stricter volatility scaling
        min_volume = base_min_volume * volatility_factor
        if is_meme:
            min_volume *= 2.0  # Much higher volume requirement for meme coins

        if market_data["volume"] < min_volume:
            if market_data["volume"] < min_volume * 0.4:  # Reject extremely low volume
                return {
                    "is_valid": False,
                    "reason": "Insufficient trading volume - trade rejected",
                    "recommendations": [
                        f"Current volume ({market_data['volume']:.0f}) below minimum ({min_volume * 0.4:.0f})",
                        "Wait for higher market activity",
                        "Consider major trading pairs",
                        f"Required volume: {min_volume:.0f}",
                    ],
                    "market_data": market_data,
                    "market_impact": market_impact,
                    "expected_slippage": expected_slippage,
                    "market_conditions_alignment": 0.1,
                }
            vol_scale = max(
                0.3, market_data["volume"] / min_volume
            )  # Stricter volume scaling
            position_scale *= vol_scale
            market_conditions.append(
                {
                    "condition": "volume",
                    "status": "warning",
                    "message": f"Low volume - position scaled to {vol_scale:.0%}",
                    "scale": vol_scale,
                }
            )

        max_spread = self.config.MAX_SLIPPAGE * (3.0 if is_meme else 2.0)
        if market_data["spread"] > max_spread:
            spread_scale = max(
                0.4, 1.0 - (market_data["spread"] - max_spread) / max_spread
            )
            position_scale *= spread_scale
            market_conditions.append(
                {
                    "condition": "spread",
                    "status": "info",
                    "message": f"Wide spread - position scaled to {spread_scale:.0%}",
                    "scale": spread_scale,
                }
            )

        # Calculate final market conditions alignment with stricter penalties
        market_conditions_alignment = 1.0
        warning_count = 0
        info_count = 0

        for condition in market_conditions:
            if condition["status"] == "warning":
                market_conditions_alignment *= 0.7  # Stricter penalty for warnings
                warning_count += 1
            elif condition["status"] == "info":
                market_conditions_alignment *= 0.85  # Stricter penalty for infos
                info_count += 1

        # Reject if too many warnings or combined warnings/infos
        if warning_count >= 2 or (warning_count + info_count) >= 4:
            return {
                "is_valid": False,
                "reason": "Multiple market condition warnings - trade rejected",
                "recommendations": [
                    f"Found {warning_count} warnings and {info_count} alerts",
                    "Market conditions are unfavorable",
                    "Wait for better market conditions",
                    *[c["message"] for c in market_conditions],
                ],
                "market_data": market_data,
                "market_impact": market_impact,
                "expected_slippage": expected_slippage,
                "market_conditions_alignment": market_conditions_alignment,
            }

        # Reject if alignment is too low
        if market_conditions_alignment < 0.5:
            return {
                "is_valid": False,
                "reason": "Poor market conditions alignment - trade rejected",
                "recommendations": [
                    f"Market alignment ({market_conditions_alignment:.2f}) below threshold (0.5)",
                    "Multiple unfavorable conditions detected",
                    *[c["message"] for c in market_conditions],
                ],
                "market_data": market_data,
                "market_impact": market_impact,
                "expected_slippage": expected_slippage,
                "market_conditions_alignment": market_conditions_alignment,
            }

        return {
            "is_valid": True,
            "reason": "Market conditions assessed - proceeding with adjustments",
            "market_data": market_data,
            "market_impact": market_impact,
            "expected_slippage": expected_slippage,
            "position_scale": position_scale,
            "market_conditions_alignment": market_conditions_alignment,
            "recommendations": (
                [c["message"] for c in market_conditions]
                if market_conditions
                else ["Market conditions acceptable"]
            ),
            "scale_factors": {
                c["condition"]: c.get("scale", 1.0) for c in market_conditions
            },
        }

    async def _calculate_risk_metrics(
        self, params: Dict[str, Any], position_size: float
    ) -> Dict[str, Any]:
        """Calculate risk metrics including position adjustments and portfolio limits."""
        try:
            # Apply meme coin adjustments if needed
            params = await self.adjust_for_meme_coins(
                params, {"is_meme": params.get("is_meme_coin", False)}
            )
            symbol = str(params.get("symbol", "BTC/USD"))
            is_buy = params.get("side", "buy").lower() == "buy"
            is_meme = bool(params.get("is_meme_coin", False))
            price = float(params.get("price", 50000.0))
            volatility = float(params.get("volatility", 1.0))
            liquidity = float(params.get("liquidity", self.config.MIN_LIQUIDITY))
            volume = float(
                params.get("volume", liquidity * 0.05)
            )  # Reduced default volume requirement
            spread = float(params.get("spread", 0.001))
            account_size = float(params.get("account_size", 100000.0))
            leverage = float(params.get("leverage", 1.0))
            stop_loss = float(
                params.get("stop_loss", price * (0.98 if is_buy else 1.02))
            )
            take_profit = float(
                params.get("take_profit", price * (1.03 if is_buy else 0.97))
            )

            # More lenient volume validation
            min_volume = max(
                1000, position_size * price * 0.5
            )  # Only require 0.5x position value in volume
            if volume < min_volume:
                volume = min_volume  # Auto-adjust volume to minimum required

            # Validate leverage
            if leverage > self.config.MAX_LEVERAGE:
                return {
                    "is_valid": False,
                    "confidence": 0.95,
                    "risk_level": 1.0,
                    "max_loss": 0.0,
                    "position_size": 0.0,
                    "volatility_exposure": volatility,
                    "expected_return": 0.0,
                    "risk_reward_ratio": 0.0,
                    "market_conditions_alignment": 0.0,
                    "recommendations": ["Invalid trade parameters"],
                    "reason": "Invalid trade parameters: leverage too high",
                    "take_profit_levels": None,
                    "trailing_stop_level": None,
                    "dynamic_position_size": None,
                    "market_impact": 0.0,
                    "slippage": 0.0,
                    "expected_slippage": 0.0,
                    "margin_requirements": {"required": 0.0, "available": 0.0},
                    "correlation_factor": 0.0,
                    "liquidity_score": 0.0,
                    "volume_profile": {},
                }

            # Calculate position value and risk metrics
            position_value = position_size * price
            risk_per_trade = position_value / account_size

            # Market impact calculation
            base_impact = (
                (position_value / liquidity) if liquidity > 0 else float("inf")
            )
            volume_scale = (
                min(0.5, volume / (position_value * 1000))
                if position_value > 0
                else 0.1
            )
            volatility_scale = min(1.02, 1.0 + volatility * 0.01)
            market_impact = round(
                base_impact * volume_scale * volatility_scale * 0.1, 6
            )

            # Slippage calculation
            base_slippage = market_impact + (spread * 0.1)
            volume_factor = (
                max(0.95, min(1.05, volume / (position_value * 100)))
                if position_value > 0
                else 1.0
            )
            expected_slippage = round(base_slippage / volume_factor, 6)

            if is_meme:
                expected_slippage *= 1.5
                market_impact *= 1.3

            # Risk/reward calculation
            max_loss = abs(price - stop_loss) * position_size
            expected_return = abs(take_profit - price) * position_size
            risk_reward_ratio = expected_return / max_loss if max_loss > 0 else 0.0

            # Enhanced take profit calculations with fixed percentages
            volatility_factor = min(
                1.5, max(1.0, volatility / self.config.VOLATILITY_SCALE_THRESHOLD)
            )
            stop_loss_pct = self.config.STOP_LOSS_MULTIPLIER * volatility_factor * 0.01
            take_profit_pcts = [0.033, 0.05, 0.10]

            take_profit_levels = [
                round(price * (1 + pct if is_buy else 1 - pct))
                for pct in take_profit_pcts
            ]

            stop_loss = price * (1 - stop_loss_pct if is_buy else 1 + stop_loss_pct)

            # Use first take profit level for trailing stop
            trailing_stop = price * (
                1 + (take_profit_pcts[0] * self.config.TRAILING_STOP_ACTIVATION)
                if is_buy
                else 1 - (take_profit_pcts[0] * self.config.TRAILING_STOP_ACTIVATION)
            )

            # Strict volatility check
            if volatility > self.config.VOLATILITY_SCALE_THRESHOLD * 2:
                return {
                    "is_valid": False,
                    "confidence": 0.95,
                    "risk_level": 0.9,
                    "max_loss": max_loss,
                    "position_size": 0.0,
                    "volatility_exposure": volatility,
                    "expected_return": 0.0,
                    "risk_reward_ratio": 0.0,
                    "market_conditions_alignment": 0.1,
                    "recommendations": [
                        f"Extreme volatility: {volatility:.2f}",
                        f"Maximum allowed: {self.config.VOLATILITY_SCALE_THRESHOLD * 2.0:.2f}",
                        "Wait for market stabilization",
                    ],
                    "reason": "Market conditions unfavorable - extreme volatility",
                    "take_profit_levels": None,
                    "trailing_stop_level": None,
                    "dynamic_position_size": None,
                    "market_impact": market_impact,
                    "expected_slippage": expected_slippage,
                    "margin_requirements": {"required": 0.0, "available": 0.0},
                    "correlation_factor": 0.0,
                    "liquidity_score": liquidity,
                    "volume_profile": {"volume": volume},
                }

            # Risk metrics calculation with strict validation
            max_loss = position_value * stop_loss_pct
            take_profit_weights = [0.5, 0.3, 0.2]
            expected_returns = [
                position_value * (abs(tp - price) / price) * weight
                for tp, weight in zip(take_profit_levels, take_profit_weights)
            ]
            expected_return = sum(expected_returns)
            risk_reward_ratio = expected_return / max_loss if max_loss > 0 else 0.0

            # Strict risk/reward validation
            if risk_reward_ratio < 2.0 and not is_meme:
                return {
                    "is_valid": False,
                    "confidence": 0.95,
                    "risk_level": 0.8,
                    "max_loss": max_loss,
                    "position_size": position_size,
                    "volatility_exposure": volatility,
                    "expected_return": expected_return,
                    "risk_reward_ratio": risk_reward_ratio,
                    "market_conditions_alignment": 0.3,
                    "recommendations": [
                        f"Insufficient risk/reward ratio: {risk_reward_ratio:.2f}",
                        "Minimum required: 2.0",
                        "Consider adjusting entry price",
                        "Wait for better setup",
                    ],
                    "reason": "Risk/reward ratio below minimum threshold",
                    "take_profit_levels": take_profit_levels,
                    "trailing_stop_level": trailing_stop,
                    "dynamic_position_size": position_size,
                    "market_impact": market_impact,
                    "expected_slippage": expected_slippage,
                    "margin_requirements": {"required": 0.0, "available": 0.0},
                    "correlation_factor": 0.0,
                    "liquidity_score": liquidity,
                    "volume_profile": {"volume": volume},
                }

            # Market condition adjustments
            volume_factor = (
                min(1.0, volume / (position_value * 10)) if position_value > 0 else 0.5
            )
            liquidity_factor = (
                min(1.0, liquidity / (position_value * 100))
                if position_value > 0
                else 0.5
            )
            volatility_factor = max(0.5, 1.0 - volatility * 0.2)
            risk_reward_ratio *= volume_factor * liquidity_factor * volatility_factor

            if risk_reward_ratio < 2.0:
                self._add_recommendation(
                    f"Risk/reward ratio ({risk_reward_ratio:.2f}) below minimum 2.0"
                )
                self._add_recommendation(
                    "Consider adjusting entry price or take-profit levels"
                )

            # Correlation adjustment with strict validation
            correlation = await self._is_correlated(params)
            if correlation > 0.5:  # Lower threshold for correlation
                correlation_penalty = correlation * 0.5  # Stronger penalty
                risk_reward_ratio *= 1.0 - correlation_penalty
                expected_return *= 1.0 - correlation_penalty
                if correlation > 0.8:  # Critical correlation level
                    return {
                        "is_valid": False,
                        "confidence": 0.95,
                        "risk_level": 0.9,
                        "max_loss": max_loss,
                        "position_size": 0.0,
                        "volatility_exposure": volatility,
                        "expected_return": 0.0,
                        "risk_reward_ratio": 0.0,
                        "market_conditions_alignment": 0.1,
                        "recommendations": [
                            f"Critical correlation level ({correlation:.1%})",
                            "Trade rejected - excessive portfolio correlation",
                            "Consider alternative markets",
                        ],
                        "reason": "Excessive portfolio correlation",
                        "take_profit_levels": None,
                        "trailing_stop_level": None,
                        "dynamic_position_size": None,
                    }

            # Position size adjustments with strict volatility limits
            adjusted_position = position_size
            if volatility > self.config.VOLATILITY_SCALE_THRESHOLD:
                if volatility > self.config.VOLATILITY_SCALE_THRESHOLD * 2.0:
                    return {
                        "is_valid": False,
                        "confidence": 0.95,
                        "risk_level": 0.9,
                        "max_loss": max_loss,
                        "position_size": 0.0,
                        "volatility_exposure": volatility,
                        "expected_return": 0.0,
                        "risk_reward_ratio": 0.0,
                        "market_conditions_alignment": 0.1,
                        "recommendations": [
                            f"Extreme volatility: {volatility:.2f}",
                            f"Maximum allowed: {self.config.VOLATILITY_SCALE_THRESHOLD * 2.0:.2f}",
                            "Wait for market stabilization",
                        ],
                        "reason": "Market conditions unfavorable - extreme volatility",
                        "take_profit_levels": None,
                        "trailing_stop_level": None,
                        "dynamic_position_size": None,
                    }
                volatility_scale = self.config.POSITION_REDUCTION_RATE
                adjusted_position *= volatility_scale
                self._add_recommendation(
                    f"High volatility ({volatility:.2f}) - position reduced by {(1-volatility_scale)*100:.0f}%"
                )
            if is_meme:
                adjusted_position *= 0.5  # Additional reduction for meme tokens
                self._add_recommendation(
                    "Meme coin detected - applying 50% position reduction"
                )
                self._add_recommendation("Higher volatility expected for meme coins")
                self._add_recommendation("Consider using tighter stops for meme coins")

            # Portfolio metrics
            existing_positions = params.get("existing_positions", [])
            total_exposure = sum(
                float(pos.get("amount", 0)) * float(pos.get("price", 0))
                for pos in existing_positions
            )
            unrealized_pnl = sum(
                float(pos.get("unrealized_pnl", 0)) for pos in existing_positions
            )

            # Margin calculations
            base_margin = (adjusted_position * price) / leverage
            volatility_margin = base_margin * (1.0 + max(0, volatility - 1.0) * 0.2)
            correlation_margin = base_margin * (1.0 + correlation * 0.3)
            margin_required = max(volatility_margin, correlation_margin)
            maintenance_margin = margin_required * (0.5 + correlation * 0.1)

            # Risk level calculation
            risk_level = min(
                1.0,
                max(
                    0.1,
                    volatility_factor * 0.5
                    + (market_impact * 2)
                    + (expected_slippage * 5)
                    + (correlation * 0.3),
                ),
            )

            # Drawdown check
            drawdown_pct = abs(unrealized_pnl / account_size) if account_size > 0 else 0
            if drawdown_pct > self.config.MAX_DRAWDOWN:
                return {
                    "is_valid": False,
                    "confidence": 0.9,
                    "risk_level": 0.9,
                    "max_loss": 0,
                    "position_size": 0,
                    "volatility_exposure": volatility,
                    "expected_return": 0,
                    "risk_reward_ratio": 0,
                    "market_conditions_alignment": 0,
                    "recommendations": [
                        f"Maximum drawdown limit reached: {drawdown_pct:.1%}",
                        "Close existing losing positions",
                        "Wait for portfolio recovery",
                        "Consider reducing leverage",
                    ],
                    "reason": "Portfolio drawdown limit exceeded",
                    "take_profit_levels": None,
                    "trailing_stop_level": None,
                    "dynamic_position_size": None,
                    "market_impact": market_impact,
                    "expected_slippage": expected_slippage,
                    "margin_requirements": {
                        "required": margin_required,
                        "maintenance": maintenance_margin,
                    },
                }

            metrics = {
                "is_valid": True,
                "confidence": 0.85,
                "risk_level": risk_level,
                "max_loss": max_loss,
                "position_size": position_size,
                "volatility_exposure": volatility,
                "expected_return": expected_return,
                "risk_reward_ratio": risk_reward_ratio,
                "market_conditions_alignment": 1.0
                - (market_impact + expected_slippage),
                "take_profit_levels": take_profit_levels,
                "trailing_stop": trailing_stop,
                "adjusted_position": adjusted_position,
                "market_impact": market_impact,
                "expected_slippage": expected_slippage,
                "margin_requirements": {
                    "required": margin_required,
                    "maintenance": maintenance_margin,
                    "available": account_size * 0.8,
                },
                "correlation_factor": correlation,
                "liquidity_score": min(1.0, liquidity / (position_value * 100)),
                "volume_profile": {
                    "volume": volume,
                    "liquidity": liquidity,
                    "turnover": volume * price,
                },
            }

            # Add recommendations
            recommendations = []
            if market_impact > self.config.MAX_SLIPPAGE * 0.5:
                recommendations.append(
                    f"High market impact detected: {market_impact:.4f}"
                )
            if volume < position_value * 5:
                recommendations.append(f"Low volume relative to position: {volume:.0f}")
            if volatility > self.config.VOLATILITY_SCALE_THRESHOLD * 2:
                recommendations.append(f"High volatility detected: {volatility:.2f}")
            if adjusted_position < position_size:
                recommendations.append(
                    f"Position size reduced to {adjusted_position:.4f} due to risk factors"
                )

            metrics["recommendations"] = recommendations
            return metrics

        except Exception as e:
            logger.error(f"Error calculating risk metrics: {str(e)}")
            return {
                "is_valid": False,
                "confidence": 0.0,
                "risk_level": 1.0,
                "recommendations": ["Risk calculation error", str(e)],
                "reason": f"Error calculating risk metrics: {str(e)}",
            }

        # Strict market condition validation
        if liquidity < self.config.MIN_LIQUIDITY:
            liquidity_ratio = liquidity / self.config.MIN_LIQUIDITY
            if liquidity_ratio < 0.8:  # Stricter liquidity requirement
                metrics.update(
                    {
                        "is_valid": False,
                        "confidence": 0.95,
                        "risk_level": 0.9,
                        "max_loss": max_loss,
                        "position_size": metrics.get("position_size", 0.0)
                        * liquidity_ratio,
                        "volatility_exposure": volatility,
                        "expected_return": expected_return * liquidity_ratio,
                        "risk_reward_ratio": risk_reward_ratio * liquidity_ratio,
                        "market_conditions_alignment": liquidity_ratio,
                        "recommendations": [
                            f"Critical liquidity: {liquidity:.0f} < {self.config.MIN_LIQUIDITY:.0f}",
                            "Consider smaller position size",
                            "Use limit orders to minimize impact",
                            "Monitor execution carefully",
                        ],
                        "reason": "Insufficient market liquidity",
                        "take_profit_levels": take_profit_levels,
                        "trailing_stop_level": trailing_stop,
                        "dynamic_position_size": adjusted_position
                        * max(0.3, liquidity_ratio),
                        "market_impact": market_impact,
                        "expected_slippage": expected_slippage,
                        "margin_requirements": {
                            "required": margin_required * liquidity_ratio,
                            "available": account_size,
                        },
                    }
                )

        if market_impact > self.config.MAX_SLIPPAGE * 2:
            metrics.update(
                {
                    "is_valid": False,
                    "confidence": 0.9,
                    "risk_level": 0.8,
                    "max_loss": max_loss,
                    "position_size": metrics.get("position_size", 0.0),
                    "volatility_exposure": volatility,
                    "expected_return": expected_return,
                    "risk_reward_ratio": risk_reward_ratio,
                    "market_conditions_alignment": 0.3,
                    "recommendations": [
                        "Poor market conditions",
                        "High market impact detected",
                        f"Current impact: {market_impact:.4f}",
                        "Consider reducing order size",
                        "Use limit orders to minimize impact",
                    ],
                    "reason": "Poor market conditions - high market impact",
                    "take_profit_levels": take_profit_levels,
                    "trailing_stop_level": trailing_stop,
                    "dynamic_position_size": adjusted_position * 0.5,
                    "market_impact": market_impact,
                    "expected_slippage": expected_slippage,
                    "margin_requirements": {
                        "required": margin_required,
                        "available": account_size,
                    },
                }
            )

        # Calculate correlation factor with strict position reduction
        correlation = await self._is_correlated(params)
        if correlation > 0.5:
            reduction_factor = 1.0 - (
                correlation - 0.5
            )  # Linear reduction from 0.5 to 1.0
            adjusted_position *= reduction_factor
            logger.info(
                f"Reducing position size to {reduction_factor:.2%} due to correlation: {correlation:.2f}"
            )
            self._add_recommendation(
                f"Position reduced due to {correlation:.1%} correlation"
            )
            self._add_recommendation(
                "Consider alternative markets to reduce correlation"
            )

        # Calculate risk metrics with improved risk/reward calculation
        max_loss = abs(price - stop_loss) * adjusted_position
        take_profit_weights = [0.5, 0.3, 0.2]  # Higher weight for closer targets
        expected_returns = [
            abs(tp - price)
            * adjusted_position
            * weight
            * (1.0 + (0.2 if is_meme else 0))
            for tp, weight in zip(take_profit_levels, take_profit_weights)
        ]
        expected_return = sum(expected_returns)

        # Calculate risk/reward with enhanced market condition adjustments
        base_risk_reward = expected_return / max_loss if max_loss > 0 else 2.0
        volume_bonus = min(0.5, volume / 50000) if volume > 0 else 0
        liquidity_bonus = min(0.3, liquidity / 500000) if liquidity > 0 else 0
        volatility_penalty = (
            max(0, min(0.3, (volatility - 1.0) / 2)) if volatility > 1.0 else 0
        )

        risk_reward = base_risk_reward * (
            2.0 + volume_bonus + liquidity_bonus - volatility_penalty
        )
        if is_meme:
            risk_reward *= 1.5  # More aggressive for meme coins

        # Log risk metrics for debugging
        logger.debug(
            f"Risk metrics: max_loss={max_loss}, expected_return={expected_return}, "
            f"risk_reward={risk_reward}, market_impact={market_impact}, "
            f"slippage={expected_slippage}, take_profit_levels={take_profit_levels}"
        )

        logger.info(
            f"Risk metrics calculated - Risk/Reward: {risk_reward:.2f}, "
            f"Position: {adjusted_position:.2f}, Stop: {stop_loss:.2f}, "
            f"Take Profits: {take_profit_levels}"
        )

        # Enhanced market data source and staleness tracking
        market_data_source = params.get("market_data_source", "live")
        is_stale = params.get("is_stale", False)

        # Add rate limit tracking
        rate_key = f"ratelimit:market:{symbol}"
        rate_limit_info = await self._check_rate_limit(rate_key)
        if rate_limit_info["remaining"] < rate_limit_info["limit"] * 0.2:
            self._add_recommendation(
                "Approaching rate limit - consider reducing request frequency"
            )

        # Calculate final risk level with more lenient thresholds for meme coins
        risk_level = 1 - risk_reward if risk_reward <= 1 else 0.5
        if is_meme:
            risk_level = min(risk_level * 0.8, 0.95)  # More lenient for meme coins

        return RiskAssessment(
            is_valid=True,
            confidence=0.95,
            risk_level=risk_level,
            max_loss=max_loss,
            position_size=position_size,
            volatility_exposure=volatility,
            expected_return=expected_return,
            risk_reward_ratio=risk_reward,
            market_conditions_alignment=1.0 - (market_impact + expected_slippage),
            recommendations=self._recommendations,
            reason="Risk metrics calculated successfully",
            take_profit_levels=take_profit_levels,
            trailing_stop_level=trailing_stop,
            dynamic_position_size=adjusted_position,
            market_impact=market_impact,
            slippage=spread,
            expected_slippage=expected_slippage,
            margin_requirements={
                "required": margin_required,
                "maintenance": maintenance_margin,
            },
            correlation_factor=correlation,
            liquidity_score=liquidity,
            volume_profile={
                "volume": volume,
                "liquidity": liquidity,
                "turnover": volume * price,
            },
            market_data_source=market_data_source,
            is_stale=is_stale,
            rate_limit_info={"is_limited": False, "remaining": 100, "reset": 0.0},
        )

    async def _validate_risk_metrics(self, metrics: Dict[str, Any]) -> RiskAssessment:
        """Validate risk metrics with strict thresholds."""
        try:
            reasons = []
            is_meme = metrics.get("is_meme_coin", False)
            volatility = float(metrics.get("volatility", 1.0))
            position_size = float(metrics.get("position_size", 0.0))
            dynamic_position_size = float(
                metrics.get("dynamic_position_size", position_size)
            )
            market_impact = float(metrics.get("market_impact", 0.0))
            expected_slippage = float(metrics.get("expected_slippage", 0.0))
            liquidity_score = float(metrics.get("liquidity", 0.0))
            risk_reward_ratio = float(metrics.get("risk_reward", 0.0))
            max_loss = float(metrics.get("max_loss", 0.0))
            expected_return = float(metrics.get("expected_return", 0.0))
            take_profit_levels = metrics.get("take_profit_levels", [])

            # Validate basic metrics with more lenient checks
            if position_size <= 0:
                reasons.append("Invalid position size")
                reasons.append("Check account balance and leverage settings")
                return RiskAssessment(
                    is_valid=False,
                    confidence=0.9,
                    risk_level=0.9,
                    max_loss=max_loss,
                    position_size=0.0,
                    volatility_exposure=volatility,
                    expected_return=expected_return,
                    risk_reward_ratio=risk_reward_ratio,
                    market_conditions_alignment=0.2,
                    recommendations=reasons,
                    reason="Invalid position size",
                    take_profit_levels=None,
                    trailing_stop_level=None,
                    dynamic_position_size=0.0,
                    market_impact=market_impact,
                    slippage=0.0,
                    expected_slippage=expected_slippage,
                    margin_requirements=self._metrics.get("margin_requirements", {}),
                    correlation_factor=0.0,
                    liquidity_score=liquidity_score,
                    volume_profile=self._metrics.get("volume_profile", {}),
                    market_data_source="live",
                    is_stale=False,
                    rate_limit_info={
                        "is_limited": False,
                        "remaining": 100,
                        "reset": 0.0,
                    },
                )
            # Get margin requirements
            margin_requirements = metrics.get("margin_requirements", {})
            margin_used = float(margin_requirements.get("used", 0.0))
            margin_available = float(margin_requirements.get("available", float("inf")))
            account_size = float(metrics.get("account_size", 100000.0))

            # Calculate margin ratio
            margin_ratio = margin_used / account_size if account_size > 0 else 0.0

            # Validate margin utilization
            if margin_ratio > 0.85:  # Maximum 85% margin utilization
                reasons.append("Trade rejected - excessive margin utilization")
                reasons.append("Close existing positions first")
                reasons.append(f"Current margin ratio: {margin_ratio:.0%}")
                reasons.append("Maximum allowed: 85%")
                return RiskAssessment(
                    is_valid=False,
                    confidence=0.9,
                    risk_level=0.9,
                    max_loss=max_loss,
                    position_size=0.0,
                    volatility_exposure=volatility,
                    expected_return=expected_return,
                    risk_reward_ratio=risk_reward_ratio,
                    market_conditions_alignment=0.2,
                    recommendations=reasons,
                    reason="Market conditions unfavorable - high margin usage",
                    take_profit_levels=None,
                    trailing_stop_level=None,
                    dynamic_position_size=0.0,
                    market_impact=market_impact,
                    slippage=0.0,
                    expected_slippage=expected_slippage,
                    margin_requirements=margin_requirements,
                    correlation_factor=0.0,
                    liquidity_score=liquidity_score,
                    volume_profile={},
                    market_data_source="live",
                    is_stale=False,
                    rate_limit_info={
                        "is_limited": False,
                        "remaining": 100,
                        "reset": 0.0,
                    },
                )

            # Strict market conditions validation
            market_check = await self._check_market_conditions(self._metrics)
            market_alignment = market_check.get("market_conditions_alignment", 0.0)

            # Reject trades in poor market conditions
            if market_alignment < 0.6 or not market_check.get("is_valid", False):
                return RiskAssessment(
                    is_valid=False,
                    confidence=0.95,
                    risk_level=0.9,
                    max_loss=max_loss,
                    position_size=0.0,
                    volatility_exposure=volatility,
                    expected_return=0.0,
                    risk_reward_ratio=0.0,
                    market_conditions_alignment=market_alignment,
                    recommendations=[
                        "Market conditions highly unfavorable",
                        f"Market alignment: {market_alignment:.2f}",
                        "Wait for better market conditions",
                        "Consider alternative trading pairs",
                    ]
                    + market_check.get("recommendations", []),
                    reason="Trade rejected - poor market conditions",
                    take_profit_levels=None,
                    trailing_stop_level=None,
                    dynamic_position_size=0.0,
                    market_impact=market_impact,
                    slippage=0.0,
                    expected_slippage=expected_slippage,
                    margin_requirements=margin_requirements,
                    correlation_factor=0.0,
                    liquidity_score=liquidity_score,
                    volume_profile=self._metrics.get("volume_profile", {}),
                    market_data_source="live",
                    is_stale=False,
                    rate_limit_info={
                        "is_limited": False,
                        "remaining": 100,
                        "reset": 0.0,
                    },
                )
            margin_requirements = self._metrics.get("margin_requirements", {})
            margin_ratio = margin_requirements.get("ratio", 0.0)
            margin_used = margin_requirements.get("used", 0.0)
            margin_available = margin_requirements.get("available", float("inf"))

            # Validate margin utilization
            if margin_ratio > 0.85:  # Maximum 85% margin utilization
                reasons.append("Trade rejected - excessive margin utilization")
                reasons.append("Close existing positions first")
                reasons.append(f"Current margin ratio: {margin_ratio:.0%}")
                reasons.append("Maximum allowed: 85%")
                return RiskAssessment(
                    is_valid=False,
                    confidence=0.9,
                    risk_level=0.9,
                    max_loss=max_loss,
                    position_size=position_size,
                    volatility_exposure=volatility,
                    expected_return=expected_return,
                    risk_reward_ratio=risk_reward_ratio,
                    market_conditions_alignment=0.2,
                    recommendations=reasons,
                    reason="Market conditions unfavorable - high margin usage",
                    take_profit_levels=None,
                    trailing_stop_level=None,
                    dynamic_position_size=dynamic_position_size,
                    market_impact=market_impact,
                    slippage=0.0,
                    expected_slippage=expected_slippage,
                    margin_requirements=margin_requirements,
                    correlation_factor=0.0,
                    liquidity_score=liquidity_score,
                    volume_profile=self._metrics.get("volume_profile", {}),
                    market_data_source="live",
                    is_stale=False,
                    rate_limit_info={
                        "is_limited": False,
                        "remaining": 100,
                        "reset": 0.0,
                    },
                )

            # Adaptive validation thresholds
            risk_threshold = 0.85 if is_meme else 0.75
            volatility_threshold = 2.5 if is_meme else 2.0
            impact_threshold = self.config.MAX_SLIPPAGE * (2.0 if is_meme else 1.5)
            slippage_threshold = self.config.MAX_SLIPPAGE * (2.0 if is_meme else 1.5)
            liquidity_threshold = self.config.MIN_LIQUIDITY * (0.3 if is_meme else 0.5)
            reward_threshold = 1.5 if is_meme else 2.0

            # Adaptive risk validation with volume-based scaling
            risk_reward = metrics.get("risk_reward_ratio", 0.0)
            market_conditions = metrics.get("market_conditions_alignment", 0.5)
            volatility = metrics.get("volatility_exposure", 1.0)
            volume = metrics.get("volume", 0.0)
            current_price = float(metrics.get("price", 0.0))
            position_value = position_size * current_price

            # More lenient volume requirements
            min_volume = (
                position_value * 0.3
            )  # Only require 30% of position value in volume
            volume_scale = max(0.3, min(1.0, volume / min_volume))

            # Scale thresholds based on volume
            base_threshold = reward_threshold * volume_scale
            volatility_adjustment = min(1.0, max(0.5, 1.0 - (volatility - 1.0) * 0.3))
            market_adjustment = 1.0 if market_conditions > 0.7 else 1.3
            final_threshold = base_threshold * volatility_adjustment * market_adjustment

            # Update position size based on volume
            if volume_scale < 1.0:
                metrics["position_size"] *= volume_scale
                metrics["dynamic_position_size"] = metrics["position_size"]
                self._add_recommendation(
                    f"Position reduced to {volume_scale:.0%} due to volume conditions"
                )

            # Reject trades with very poor risk/reward ratios immediately
            if risk_reward < final_threshold * 0.5:
                return RiskAssessment(
                    is_valid=False,
                    confidence=0.9,
                    risk_level=0.8,
                    max_loss=max_loss * 0.5,
                    position_size=0.0,
                    volatility_exposure=volatility,
                    expected_return=0.0,
                    risk_reward_ratio=risk_reward,
                    market_conditions_alignment=market_conditions,
                    recommendations=[
                        f"Critically low risk/reward ratio: {risk_reward:.2f}",
                        f"Minimum required: {final_threshold * 0.5:.1f}",
                        "Trade rejected - insufficient potential return",
                        "Consider different entry price or strategy",
                    ],
                    reason="Trade rejected - poor risk/reward ratio",
                    take_profit_levels=None,
                    trailing_stop_level=None,
                    dynamic_position_size=0.0,
                    market_impact=market_impact,
                    expected_slippage=expected_slippage,
                    margin_requirements={"required": 0.0, "maintenance": 0.0},
                    correlation_factor=0.0,
                    liquidity_score=liquidity_score,
                    volume_profile={},
                )

            if risk_reward < final_threshold:
                reasons.append(
                    f"Risk/reward ratio ({risk_reward:.2f}) below required target {final_threshold:.1f}"
                )
                if (
                    risk_reward < final_threshold * 0.8
                ):  # Stricter threshold for rejection
                    return RiskAssessment(
                        is_valid=False,
                        confidence=0.85,
                        risk_level=0.7,
                        max_loss=metrics.get("max_loss", 0.0),
                        position_size=metrics.get("position_size", 0.0) * 0.5,
                        volatility_exposure=metrics.get("volatility_exposure", 1.0),
                        expected_return=metrics.get("expected_return", 0.0),
                        risk_reward_ratio=risk_reward,
                        market_conditions_alignment=market_conditions,
                        recommendations=[
                            f"Low risk/reward ratio: {risk_reward:.2f}",
                            f"Target ratio: {final_threshold:.1f}",
                            "Consider adjusting entry price or take-profit levels",
                            "Reduce position size or wait for better setup",
                        ],
                        reason="Risk/reward ratio significantly below target",
                        take_profit_levels=metrics.get("take_profit_levels"),
                        trailing_stop_level=metrics.get("trailing_stop_level"),
                        dynamic_position_size=metrics.get("position_size", 0.0) * 0.5,
                    )

            # Market impact validation with stricter thresholds
            market_impact = metrics.get("market_impact", 0.0)
            if (
                market_impact > impact_threshold * 0.8
            ):  # Lower threshold for impact scaling
                # Calculate position reduction based on impact more aggressively
                impact_scale = max(
                    0.1, 1.0 - (market_impact - impact_threshold * 0.8) * 2.0
                )
                scaled_position = position_size * impact_scale

                if (
                    market_impact > impact_threshold * 0.9
                ):  # Reject before reaching max threshold
                    return RiskAssessment(
                        is_valid=False,
                        confidence=0.8,
                        risk_level=0.6,
                        max_loss=max_loss * impact_scale,
                        position_size=scaled_position,
                        volatility_exposure=metrics.get("volatility_exposure", 1.0),
                        expected_return=expected_return * impact_scale,
                        risk_reward_ratio=risk_reward_ratio,
                        market_conditions_alignment=0.4,
                        recommendations=[
                            f"High market impact: {market_impact:.4f}",
                            f"Position reduced to {impact_scale:.0%}",
                            "Consider using time-weighted execution",
                            "Split order into smaller parts",
                            f"Target impact: {impact_threshold:.4f}",
                        ],
                        reason="Position size reduced due to market impact",
                        take_profit_levels=take_profit_levels,
                        trailing_stop_level=metrics.get("trailing_stop_level"),
                        dynamic_position_size=scaled_position,
                        market_impact=market_impact,
                        expected_slippage=metrics.get("expected_slippage", 0.0),
                        margin_requirements=metrics.get(
                            "margin_requirements", {"required": 0.0, "available": 0.0}
                        ),
                        correlation_factor=metrics.get("correlation_factor", 0.0),
                        liquidity_score=metrics.get("liquidity_score", 0.0),
                        volume_profile=metrics.get("volume_profile", {}),
                    )
                else:
                    metrics["position_size"] = scaled_position
                    metrics["dynamic_position_size"] = scaled_position
                    self._add_recommendation(
                        f"Position reduced to {impact_scale:.0%} due to market impact"
                    )

            # Ultra-strict slippage validation with aggressive scaling
            expected_slippage = metrics.get("expected_slippage", 0.0)
            if (
                expected_slippage > self.config.MAX_SLIPPAGE * 0.5
            ):  # Much lower threshold for scaling
                slippage_scale = max(
                    0.1,
                    1.0 - (expected_slippage - self.config.MAX_SLIPPAGE * 0.5) * 3.0,
                )
                scaled_position = position_size * slippage_scale
                metrics["position_size"] = scaled_position
                metrics["dynamic_position_size"] = scaled_position
                reasons.append(
                    f"Position reduced to {slippage_scale:.0%} due to high slippage"
                )

                if (
                    expected_slippage > self.config.MAX_SLIPPAGE * 0.8
                ):  # Reject at lower threshold
                    return RiskAssessment(
                        is_valid=False,
                        confidence=0.85,
                        risk_level=0.7,
                        max_loss=metrics.get("max_loss", 0.0) * slippage_scale,
                        position_size=scaled_position,
                        volatility_exposure=metrics.get("volatility_exposure", 1.0),
                        expected_return=metrics.get("expected_return", 0.0)
                        * slippage_scale,
                        risk_reward_ratio=metrics.get("risk_reward_ratio", 0.0),
                        market_conditions_alignment=0.3,
                        recommendations=[
                            f"High slippage detected: {expected_slippage:.4f}",
                            f"Position reduced to {slippage_scale:.0%}",
                            "Use limit orders to minimize impact",
                            "Consider splitting order into smaller parts",
                        ],
                        reason="Position size reduced due to high slippage",
                        take_profit_levels=metrics.get("take_profit_levels"),
                        trailing_stop_level=metrics.get("trailing_stop_level"),
                        dynamic_position_size=scaled_position,
                        market_impact=metrics.get("market_impact", 0.0),
                        expected_slippage=expected_slippage,
                        margin_requirements={"required": 0.0, "maintenance": 0.0},
                        correlation_factor=0.0,
                        liquidity_score=0.0,
                        volume_profile={},
                    )

            # Adaptive liquidity validation with progressive scaling
            liquidity_score = metrics.get("liquidity_score", 0.0)
            volume = metrics.get("volume", 0.0)
            price = float(metrics.get("price", 0.0))
            min_volume = (
                position_size * price * 0.5
            )  # Only require 0.5x position value in volume

            if volume < min_volume:
                volume_scale = max(0.3, volume / min_volume)
                scaled_position = position_size * volume_scale
                metrics["position_size"] = scaled_position
                metrics["dynamic_position_size"] = scaled_position
                reasons.append(
                    f"Position reduced to {volume_scale:.0%} due to low volume"
                )

                if volume < min_volume * 0.3:  # Only reject if volume is extremely low
                    return RiskAssessment(
                        is_valid=False,
                        confidence=0.85,
                        risk_level=0.7,
                        max_loss=max_loss * volume_scale,
                        position_size=scaled_position,
                        volatility_exposure=metrics.get("volatility_exposure", 1.0),
                        expected_return=expected_return * volume_scale,
                        risk_reward_ratio=risk_reward_ratio,
                        market_conditions_alignment=0.3,
                        recommendations=[
                            f"Low liquidity detected: {liquidity_score:.0f}",
                            f"Position reduced to {(liquidity_score/100):.0%}",
                            "Use limit orders to minimize impact",
                            "Consider splitting order into smaller parts",
                        ],
                        reason="Position size reduced due to low liquidity",
                        take_profit_levels=take_profit_levels,
                        trailing_stop_level=metrics.get("trailing_stop_level"),
                        dynamic_position_size=scaled_position,
                        market_impact=metrics.get("market_impact", 0.0),
                        expected_slippage=metrics.get("expected_slippage", 0.0),
                        margin_requirements=metrics.get(
                            "margin_requirements", {"required": 0.0, "maintenance": 0.0}
                        ),
                        correlation_factor=metrics.get("correlation_factor", 0.0),
                        liquidity_score=liquidity_score,
                        volume_profile=metrics.get("volume_profile", {}),
                    )
                else:
                    metrics["position_size"] = scaled_position
                    metrics["dynamic_position_size"] = scaled_position
                    self._add_recommendation(
                        f"Position reduced to {(liquidity_score/100):.0%} due to liquidity"
                    )

            # Ultra-strict risk/reward validation with aggressive scaling
            risk_reward_ratio = metrics.get("risk_reward_ratio", 0.0)
            market_conditions = metrics.get("market_conditions_alignment", 0.5)
            volatility = metrics.get("volatility_exposure", 1.0)

            # Ultra-strict risk/reward calculation with dynamic thresholds
            stop_loss = metrics.get("stop_loss", 0.0)
            take_profit = metrics.get("take_profit", 0.0)
            price = metrics.get("price", 0.0)

            if stop_loss <= 0 or take_profit <= price:
                return RiskAssessment(
                    is_valid=False,
                    confidence=0.95,
                    risk_level=0.9,
                    max_loss=0.0,
                    position_size=0.0,
                    volatility_exposure=volatility,
                    expected_return=0.0,
                    risk_reward_ratio=0.0,
                    market_conditions_alignment=0.2,
                    recommendations=["Invalid stop-loss or take-profit levels"],
                    reason="Trade rejected - invalid risk parameters",
                    take_profit_levels=None,
                    trailing_stop_level=None,
                    dynamic_position_size=0.0,
                )

            risk_reward_ratio = (take_profit - price) / (price - stop_loss)

            # Ultra-strict dynamic threshold with comprehensive market condition adjustments
            base_threshold = reward_threshold * 3.0  # Even higher base requirement
            volatility_factor = max(
                2.0, volatility * 1.5
            )  # Much stricter volatility scaling
            market_factor = 1.0 / max(
                0.3, market_conditions
            )  # More aggressive market conditions scaling
            liquidity_factor = max(
                1.5, self.config.MIN_LIQUIDITY / max(liquidity_score, 1.0)
            )
            spread_factor = max(
                1.5, expected_slippage / max(self.config.MAX_SLIPPAGE * 0.5, 0.0001)
            )

            final_threshold = (
                base_threshold
                * volatility_factor
                * market_factor
                * liquidity_factor
                * spread_factor
            )

            if risk_reward_ratio < final_threshold:  # Reject if below threshold
                scaled_position = position_size * max(
                    0.3, risk_reward_ratio / final_threshold
                )
                return RiskAssessment(
                    is_valid=False,
                    confidence=0.85,
                    risk_level=0.7,
                    max_loss=max_loss * 0.5,
                    position_size=scaled_position,
                    volatility_exposure=volatility,
                    expected_return=expected_return * 0.5,
                    risk_reward_ratio=risk_reward_ratio,
                    market_conditions_alignment=market_conditions,
                    recommendations=[
                        f"Low risk/reward ratio: {risk_reward_ratio:.2f}",
                        f"Target ratio: {final_threshold:.1f}",
                        "Consider adjusting entry price or take-profit levels",
                        "Position size reduced due to risk/reward ratio",
                    ],
                    reason="Position size reduced - low risk/reward ratio",
                    take_profit_levels=take_profit_levels,
                    trailing_stop_level=metrics.get("trailing_stop_level"),
                    dynamic_position_size=scaled_position,
                    market_impact=metrics.get("market_impact", 0.0),
                    expected_slippage=metrics.get("expected_slippage", 0.0),
                    margin_requirements=metrics.get(
                        "margin_requirements", {"required": 0.0, "maintenance": 0.0}
                    ),
                    correlation_factor=metrics.get("correlation_factor", 0.0),
                    liquidity_score=metrics.get("liquidity_score", 0.0),
                    volume_profile=metrics.get("volume_profile", {}),
                )
            elif risk_reward_ratio < final_threshold:
                self._add_recommendation(
                    f"Risk/reward ratio ({risk_reward_ratio:.2f}) below target {final_threshold:.1f}"
                )
                self._add_recommendation(
                    "Consider adjusting entry price or take-profit levels"
                )

            # Adaptive volatility validation
            if volatility > volatility_threshold:
                # Scale position size based on volatility more aggressively
                vol_scale = max(0.2, 1.0 - (volatility - volatility_threshold) * 0.5)
                scaled_position = position_size * vol_scale

                if (
                    volatility > volatility_threshold * 1.2
                ):  # Reject on moderately high volatility
                    return RiskAssessment(
                        is_valid=False,
                        confidence=0.85,
                        risk_level=0.8,
                        max_loss=max_loss * vol_scale,
                        position_size=scaled_position,
                        volatility_exposure=volatility,
                        expected_return=expected_return * vol_scale,
                        risk_reward_ratio=risk_reward_ratio,
                        market_conditions_alignment=0.3,
                        recommendations=[
                            f"High volatility detected: {volatility:.2f}",
                            f"Position reduced to {vol_scale:.0%}",
                            "Consider using limit orders",
                            "Monitor market conditions closely",
                        ],
                        reason="Position size reduced due to high volatility",
                        take_profit_levels=take_profit_levels,
                        trailing_stop_level=metrics.get("trailing_stop_level"),
                        dynamic_position_size=scaled_position,
                        market_impact=metrics.get("market_impact", 0.0),
                        expected_slippage=metrics.get("expected_slippage", 0.0),
                        margin_requirements=metrics.get(
                            "margin_requirements", {"required": 0.0, "maintenance": 0.0}
                        ),
                        correlation_factor=metrics.get("correlation_factor", 0.0),
                        liquidity_score=metrics.get("liquidity_score", 0.0),
                        volume_profile=metrics.get("volume_profile", {}),
                    )
                else:
                    metrics["position_size"] = scaled_position
                    metrics["dynamic_position_size"] = scaled_position
                    self._add_recommendation(
                        f"Position reduced to {vol_scale:.0%} due to volatility"
                    )

            # Strict portfolio risk validation
            correlation = metrics.get("correlation_factor", 0.0)
            margin_requirements = metrics.get(
                "margin_requirements", {"required": 0.0, "available": 0.0}
            )
            margin_used = margin_requirements.get("required", 0.0)
            unrealized_pnl = metrics.get("max_loss", 0.0)
            current_position = metrics.get("position_size", 0.0)
            account_size = metrics.get("account_size", current_position * 100)

            # Reject trades that would exceed portfolio risk limits
            if margin_used / account_size > 0.75 or unrealized_pnl < -0.08:
                return RiskAssessment(
                    is_valid=False,
                    confidence=0.95,
                    risk_level=0.9,
                    max_loss=0.0,
                    position_size=0.0,
                    volatility_exposure=volatility,
                    expected_return=0.0,
                    risk_reward_ratio=0.0,
                    market_conditions_alignment=0.2,
                    recommendations=[
                        f"Portfolio risk limits exceeded",
                        f"Current margin usage: {margin_used/account_size:.1%}",
                        f"Unrealized PnL: {unrealized_pnl:.1%}",
                        "Close existing positions first",
                    ],
                    reason="Trade rejected - portfolio risk limits exceeded",
                    take_profit_levels=None,
                    trailing_stop_level=None,
                    dynamic_position_size=0.0,
                    market_impact=0.0,
                    slippage=0.0,
                    expected_slippage=0.0,
                    margin_requirements=margin_requirements,
                    correlation_factor=correlation,
                    liquidity_score=0.0,
                    volume_profile={},
                )

            # Strict correlation validation
            if correlation > 0.5:  # Lower threshold for scaling
                correlation_penalty = (
                    correlation - 0.5
                ) * 2.0  # More aggressive scaling
                scale = max(0.2, 1.0 - correlation_penalty)
                metrics["position_size"] *= scale
                metrics["dynamic_position_size"] = metrics["position_size"]
                reasons.append(
                    f"Position reduced to {scale:.0%} due to high correlation"
                )

            # Reject trades with very high correlation
            if correlation > 0.8:  # Lower threshold for rejection
                scale = max(0.1, 1.0 - (correlation - 0.8) * 3.0)  # Aggressive scaling
                scaled_position = current_position * scale
                metrics["position_size"] = scaled_position
                metrics["dynamic_position_size"] = scaled_position
                reasons.append(
                    f"Critical correlation ({correlation:.2f}) - position reduced to {scale:.0%}"
                )
                if correlation > 0.85:  # Reject at lower correlation threshold
                    return RiskAssessment(
                        is_valid=True,  # Allow trade but with warnings
                        confidence=0.7,
                        risk_level=0.6,
                        max_loss=metrics.get("max_loss", 0.0) * scale,
                        position_size=scaled_position,
                        volatility_exposure=metrics.get("volatility_exposure", 1.0),
                        expected_return=metrics.get("expected_return", 0.0) * scale,
                        risk_reward_ratio=metrics.get("risk_reward_ratio", 0.0),
                        market_conditions_alignment=0.4,
                        recommendations=[
                            f"Very high correlation ({correlation:.2f})",
                            f"Position adjusted to {scale:.0%}",
                            "Monitor portfolio correlation closely",
                            "Consider diversifying in future trades",
                        ],
                        reason="Position adjusted for correlation risk",
                        take_profit_levels=metrics.get("take_profit_levels"),
                        trailing_stop_level=metrics.get("trailing_stop_level"),
                        dynamic_position_size=scaled_position,
                        market_impact=metrics.get("market_impact", 0.0),
                        expected_slippage=metrics.get("expected_slippage", 0.0),
                        margin_requirements=margin_requirements,
                    )

            # Add drawdown warnings with adaptive PnL tracking
            if unrealized_pnl < -0.08:  # 8% drawdown
                reasons.append(f"Significant unrealized drawdown: {unrealized_pnl:.1%}")
                reasons.append("Monitor unrealized losses closely")
                if unrealized_pnl < -0.12:  # 12% drawdown
                    reasons.append("Critical unrealized losses - reduce risk exposure")
                    reasons.append("Consider closing underperforming positions")

            # Add position size recommendations
            volatility_exposure = metrics.get("volatility_exposure", 1.0)
            if volatility_exposure > 1.5:
                reasons.append("Consider reducing position size due to high volatility")
                if volatility_exposure > 2.0:
                    reasons.append(
                        "Warning: Extreme volatility - position size reduction recommended"
                    )

            # More lenient margin utilization check
            margin_ratio = (
                margin_used / account_size if account_size > 0 else float("inf")
            )
            if margin_ratio > 0.95:  # Higher threshold for rejection
                scale = max(0.3, 1.0 - (margin_ratio - 0.85))
                scaled_position = current_position * scale
                return RiskAssessment(
                    is_valid=True,  # Allow trade with reduced size
                    confidence=0.8,
                    risk_level=0.7,
                    max_loss=metrics.get("max_loss", 0.0) * scale,
                    position_size=scaled_position,
                    volatility_exposure=metrics.get("volatility_exposure", 1.0),
                    expected_return=metrics.get("expected_return", 0.0) * scale,
                    risk_reward_ratio=metrics.get("risk_reward_ratio", 0.0),
                    market_conditions_alignment=0.4,
                    recommendations=reasons
                    + [
                        f"High margin usage ({margin_ratio:.1%})",
                        f"Position reduced to {scale:.0%}",
                        "Consider closing some positions",
                        "Monitor margin levels closely",
                    ],
                    reason="Position size reduced - high margin usage",
                    take_profit_levels=metrics.get("take_profit_levels"),
                    trailing_stop_level=metrics.get("trailing_stop_level"),
                    dynamic_position_size=scaled_position,
                    market_impact=metrics.get("market_impact", 0.0),
                    expected_slippage=metrics.get("expected_slippage", 0.0),
                    margin_requirements=margin_requirements,
                    correlation_factor=correlation,
                    liquidity_score=liquidity_score,
                    volume_profile=metrics.get("volume_profile", {}),
                )

            # More lenient drawdown handling
            if unrealized_pnl < -self.config.MAX_DRAWDOWN:
                scale = max(0.3, 1.0 + unrealized_pnl / self.config.MAX_DRAWDOWN)
                scaled_position = current_position * scale
                if (
                    unrealized_pnl < -self.config.MAX_DRAWDOWN * 1.5
                ):  # Only reject on severe drawdown
                    return RiskAssessment(
                        is_valid=False,
                        confidence=0.9,
                        risk_level=0.8,
                        max_loss=0.0,
                        position_size=0.0,
                        volatility_exposure=metrics.get("volatility_exposure", 1.0),
                        expected_return=0.0,
                        risk_reward_ratio=0.0,
                        market_conditions_alignment=0.2,
                        recommendations=[
                            f"Critical drawdown: {unrealized_pnl:.1%}",
                            f"Maximum allowed: {self.config.MAX_DRAWDOWN*1.5:.1%}",
                            "Close losing positions first",
                            "Wait for portfolio recovery",
                        ],
                        reason="Trade rejected - severe drawdown",
                        take_profit_levels=None,
                        trailing_stop_level=None,
                        dynamic_position_size=0.0,
                        market_impact=metrics.get("market_impact", 0.0),
                        expected_slippage=metrics.get("expected_slippage", 0.0),
                        margin_requirements={"required": 0.0, "maintenance": 0.0},
                        correlation_factor=0.0,
                        liquidity_score=0.0,
                        volume_profile={},
                    )
                else:
                    metrics["position_size"] = scaled_position
                    metrics["dynamic_position_size"] = scaled_position
                    reasons.append(f"Position reduced to {scale:.0%} due to drawdown")

            # Adaptive volume validation with dynamic thresholds
            volume = metrics.get("volume_profile", {}).get("volume", 0)
            current_price = metrics.get("price", 0)
            current_position = metrics.get("position_size", 0)
            position_value = current_position * current_price

            # Dynamic minimum volume based on position value
            min_volume = max(
                position_value * 1.5,  # At least 1.5x position value
                self.config.MIN_LIQUIDITY * 0.3,  # Or 30% of min liquidity
            )

            if (
                volume < min_volume and position_value > 1000
            ):  # Only check significant positions
                vol_scale = max(0.6, (volume / min_volume) ** 0.5)  # Smoother scaling
                scaled_position = current_position * vol_scale
                metrics["position_size"] = scaled_position
                metrics["dynamic_position_size"] = scaled_position
                reasons.append(
                    f"Volume below optimal - position adjusted to {vol_scale:.0%}"
                )

                if (
                    volume < min_volume * 0.1 and position_value > 5000
                ):  # Only reject very low volume on large trades
                    return RiskAssessment(
                        is_valid=False,
                        confidence=0.85,
                        risk_level=0.7,
                        max_loss=metrics.get("max_loss", 0.0) * vol_scale,
                        position_size=scaled_position,
                        volatility_exposure=metrics.get("volatility_exposure", 1.0),
                        expected_return=metrics.get("expected_return", 0.0) * vol_scale,
                        risk_reward_ratio=metrics.get("risk_reward_ratio", 0.0),
                        market_conditions_alignment=0.3,
                        recommendations=[
                            f"Low trading volume for position size",
                            f"Current volume: {volume:.0f}",
                            f"Target volume: {min_volume:.0f}",
                            "Consider reducing order size",
                            "Use limit orders to minimize impact",
                        ],
                        reason="Position reduced - insufficient volume",
                        take_profit_levels=metrics.get("take_profit_levels"),
                        trailing_stop_level=metrics.get("trailing_stop_level"),
                        dynamic_position_size=scaled_position,
                        market_impact=metrics.get("market_impact", 0.0),
                        expected_slippage=metrics.get("expected_slippage", 0.0),
                        margin_requirements=metrics.get(
                            "margin_requirements", {"required": 0.0, "available": 0.0}
                        ),
                    )

            # Ultra-strict market condition validation with comprehensive checks
            market_check = await self._check_market_conditions(metrics)
            market_alignment = market_check.get("market_conditions_alignment", 0.0)
            volatility = metrics.get("volatility_exposure", 1.0)
            liquidity = metrics.get("liquidity_score", 0.0)
            spread = metrics.get("expected_slippage", 0.0)

            # Comprehensive market condition validation
            if (
                market_alignment < 0.85  # Higher alignment requirement
                or volatility
                > self.config.VOLATILITY_SCALE_THRESHOLD
                * 1.2  # Stricter volatility check
                or liquidity
                < self.config.MIN_LIQUIDITY * 1.5  # Higher liquidity requirement
                or spread > self.config.MAX_SLIPPAGE * 0.8  # Lower slippage tolerance
                or not market_check.get("is_valid", False)
            ):
                return RiskAssessment(
                    is_valid=False,
                    confidence=0.9,
                    risk_level=0.8,
                    max_loss=0.0,
                    position_size=0.0,
                    volatility_exposure=metrics.get("volatility_exposure", 1.0),
                    expected_return=0.0,
                    risk_reward_ratio=0.0,
                    market_conditions_alignment=market_alignment,
                    recommendations=[
                        f"Poor market conditions: {market_alignment:.2f}",
                        "Market conditions below required threshold (0.7)",
                        "Consider waiting for better conditions",
                        "Monitor market indicators closely",
                    ]
                    + reasons,
                    reason="Trade rejected - unfavorable market conditions",
                    take_profit_levels=None,
                    trailing_stop_level=None,
                    dynamic_position_size=0.0,
                    market_impact=0.0,
                    expected_slippage=metrics.get("expected_slippage", 0.0),
                    margin_requirements=metrics.get(
                        "margin_requirements", {"required": 0.0, "available": 0.0}
                    ),
                )
            else:
                # Scale position instead of rejecting
                scale = max(0.4, market_check.get("market_conditions_alignment", 0.5))
                scaled_position = metrics.get("position_size", 0.0) * scale
                return RiskAssessment(
                    is_valid=True,  # Allow trade with reduced size
                    confidence=0.7,
                    risk_level=0.6,
                    max_loss=metrics.get("max_loss", 0.0) * scale,
                    position_size=scaled_position,
                    volatility_exposure=metrics.get("volatility_exposure", 1.0),
                    expected_return=metrics.get("expected_return", 0.0) * scale,
                    risk_reward_ratio=metrics.get("risk_reward_ratio", 0.0),
                    market_conditions_alignment=0.4,
                    recommendations=reasons
                    + [
                        f"Market conditions suboptimal - position reduced to {scale:.0%}",
                        "Monitor trade closely",
                        "Consider using limit orders",
                    ],
                    reason="Position adjusted for market conditions",
                    take_profit_levels=metrics.get("take_profit_levels"),
                    trailing_stop_level=metrics.get("trailing_stop_level"),
                    dynamic_position_size=scaled_position,
                    market_impact=metrics.get("market_impact", 0.0),
                    expected_slippage=metrics.get("expected_slippage", 0.0),
                    margin_requirements=metrics.get(
                        "margin_requirements", {"required": 0.0, "available": 0.0}
                    ),
                )
            liquidity_score = metrics.get("liquidity_score", 0.0)
            min_volume = liquidity_score * (0.0005 if is_meme else 0.001)
            if volume < min_volume:
                reasons.append(f"Low trading volume: {volume:.0f}")
                if volume < min_volume * 0.5:
                    reasons.append("Use limit orders to minimize impact")

            # Market impact validation
            market_impact = metrics.get("market_impact", 0.0)
            if market_impact > self.config.MAX_SLIPPAGE:
                reasons.append(f"High market impact: {market_impact:.4f}")
                if market_impact > self.config.MAX_SLIPPAGE * 2:
                    reasons.append("Consider splitting order into smaller parts")

            # Ultra-lenient meme coin validation
            if is_meme:
                reasons.append("Meme coin detected - applying flexible risk controls")
                reasons.append("Using dynamic take-profit levels for volatility")
                position_size = metrics.get("position_size", 0.0)
                dynamic_position = metrics.get("dynamic_position_size", position_size)

                # Minimal base reduction
                scale = 0.8  # Only 20% reduction
                metrics["dynamic_position_size"] = dynamic_position * scale

                # More lenient volatility scaling
                if volatility > volatility_threshold:
                    vol_scale = max(
                        0.5, 1.0 - (volatility - volatility_threshold) * 0.15
                    )
                    metrics["dynamic_position_size"] *= vol_scale
                    reasons.append(
                        f"Volatility adjustment - position scaled to {vol_scale:.0%}"
                    )

                    if (
                        volatility > volatility_threshold * 2.0
                    ):  # Much higher threshold for reduction
                        scale = max(
                            0.4, 1.0 - (volatility - volatility_threshold * 2.0) * 0.3
                        )
                        scaled_position = position_size * scale
                        reasons.append(
                            f"High volatility - position adjusted to {scale:.0%}"
                        )

                        if (
                            volatility > volatility_threshold * 3.0
                        ):  # Only reduce significantly at triple threshold
                            return RiskAssessment(
                                is_valid=False,
                                confidence=0.9,
                                risk_level=0.8,
                                max_loss=metrics.get("max_loss", 0.0),
                                position_size=scaled_position,
                                volatility_exposure=volatility,
                                expected_return=metrics.get("expected_return", 0.0),
                                risk_reward_ratio=metrics.get("risk_reward_ratio", 0.0),
                                market_conditions_alignment=0.3,
                                recommendations=reasons
                                + [
                                    f"Critical volatility: {volatility:.2f}x threshold",
                                    "Consider waiting for stabilization",
                                    "Use limit orders to minimize impact",
                                ],
                                reason="Position rejected - extreme meme coin volatility",
                                take_profit_levels=metrics.get("take_profit_levels"),
                                trailing_stop_level=metrics.get("trailing_stop_level"),
                                dynamic_position_size=scaled_position,
                                market_impact=metrics.get("market_impact", 0.0),
                                expected_slippage=metrics.get("expected_slippage", 0.0),
                                margin_requirements=metrics.get(
                                    "margin_requirements",
                                    {"required": 0.0, "available": 0.0},
                                ),
                                correlation_factor=metrics.get(
                                    "correlation_factor", 0.0
                                ),
                                liquidity_score=metrics.get("liquidity_score", 0.0),
                                volume_profile=metrics.get("volume_profile", {}),
                            )

            if not reasons:
                reasons.append("Trade meets risk criteria - proceeding with execution")

            # Final comprehensive validation before approval
            if (
                metrics.get("volatility_exposure", 1.0)
                > self.config.VOLATILITY_SCALE_THRESHOLD * 1.5
                or metrics.get("market_impact", 0.0) > self.config.MAX_SLIPPAGE * 0.7
                or metrics.get("expected_slippage", 0.0)
                > self.config.MAX_SLIPPAGE * 0.7
                or metrics.get("liquidity_score", 0.0) < self.config.MIN_LIQUIDITY * 1.2
                or metrics.get("correlation_factor", 0.0) > 0.75
            ):
                return RiskAssessment(
                    is_valid=False,
                    confidence=0.95,
                    risk_level=0.9,
                    max_loss=0.0,
                    position_size=0.0,
                    volatility_exposure=metrics.get("volatility_exposure", 1.0),
                    expected_return=0.0,
                    risk_reward_ratio=0.0,
                    market_conditions_alignment=0.3,
                    recommendations=[
                        "Critical risk metrics exceeded final thresholds",
                        f"Volatility: {metrics.get('volatility_exposure', 1.0):.2f}",
                        f"Market Impact: {metrics.get('market_impact', 0.0):.4f}",
                        f"Expected Slippage: {metrics.get('expected_slippage', 0.0):.4f}",
                        f"Liquidity Score: {metrics.get('liquidity_score', 0.0):.0f}",
                        f"Correlation: {metrics.get('correlation_factor', 0.0):.2f}",
                        "Trade rejected - risk parameters outside acceptable range",
                    ],
                    reason="Trade rejected - final risk validation failed",
                    take_profit_levels=None,
                    trailing_stop_level=None,
                    dynamic_position_size=0.0,
                    market_impact=metrics.get("market_impact", 0.0),
                    expected_slippage=metrics.get("expected_slippage", 0.0),
                    margin_requirements={"required": 0.0, "available": 0.0},
                    correlation_factor=metrics.get("correlation_factor", 0.0),
                    liquidity_score=metrics.get("liquidity_score", 0.0),
                    volume_profile={},
                )

            position_size = metrics.get("position_size", 0.0)
            current_time = time.time()

            # Apply final position size reduction based on combined risk factors
            risk_scale = min(
                1.0,
                (self.config.VOLATILITY_SCALE_THRESHOLD * 1.5)
                / max(metrics.get("volatility_exposure", 1.0), 0.1),
                (self.config.MAX_SLIPPAGE * 0.7)
                / max(metrics.get("market_impact", 0.001), 0.001),
                (self.config.MAX_SLIPPAGE * 0.7)
                / max(metrics.get("expected_slippage", 0.001), 0.001),
                metrics.get("liquidity_score", 0.0) / (self.config.MIN_LIQUIDITY * 1.2),
                (0.75) / max(metrics.get("correlation_factor", 0.0), 0.1),
            )
            final_position_size = position_size * risk_scale

            # Final margin utilization check with ultra-strict thresholds
            margin_ratio = (
                margin_used / account_size if account_size > 0 else float("inf")
            )
            margin_scale = 1.0

            if margin_ratio > 0.6:  # Start scaling down at 60% utilization
                margin_scale = max(0.3, 1.0 - (margin_ratio - 0.6) * 2.0)
                final_position_size *= margin_scale
                reasons.append(
                    f"Position reduced to {margin_scale:.0%} due to high margin usage"
                )

                if margin_ratio > 0.8:  # Reject at 80% utilization
                    return RiskAssessment(
                        is_valid=False,
                        confidence=0.95,
                        risk_level=0.9,
                        max_loss=0.0,
                        position_size=0.0,
                        volatility_exposure=metrics.get("volatility_exposure", 1.0),
                        expected_return=0.0,
                        risk_reward_ratio=0.0,
                        market_conditions_alignment=0.2,
                        recommendations=[
                            f"Critical margin utilization: {margin_ratio:.1%}",
                            "Close existing positions first",
                            "Reduce leverage or position size",
                            "Wait for margin availability",
                        ],
                        reason="Trade rejected - excessive margin utilization",
                        take_profit_levels=None,
                        trailing_stop_level=None,
                        dynamic_position_size=0.0,
                        market_impact=metrics.get("market_impact", 0.0),
                        expected_slippage=metrics.get("expected_slippage", 0.0),
                        margin_requirements=margin_requirements,
                        correlation_factor=metrics.get("correlation_factor", 0.0),
                        liquidity_score=metrics.get("liquidity_score", 0.0),
                        volume_profile={},
                    )

            # Final comprehensive risk validation
            final_risk_level = max(
                0.5,  # Base risk level
                metrics.get("volatility_exposure", 1.0)
                / self.config.VOLATILITY_SCALE_THRESHOLD,
                metrics.get("market_impact", 0.0) / (self.config.MAX_SLIPPAGE * 0.5),
                metrics.get("expected_slippage", 0.0)
                / (self.config.MAX_SLIPPAGE * 0.5),
                metrics.get("correlation_factor", 0.0) * 1.2,
                1.0
                - (
                    metrics.get("liquidity_score", 0.0)
                    / (self.config.MIN_LIQUIDITY * 1.5)
                ),
            )

            # Stricter position size adjustment
            final_scale = min(
                risk_scale,
                1.0
                - (final_risk_level - 0.5)
                * 1.5,  # More aggressive scaling based on risk
                max(0.2, 1.0 - metrics.get("volatility_exposure", 1.0) * 0.3),
                max(0.2, 1.0 - metrics.get("market_impact", 0.0) * 5.0),
                max(0.2, 1.0 - metrics.get("expected_slippage", 0.0) * 5.0),
            )

            # Apply final position size reduction
            final_position_size *= final_scale

            # Add comprehensive risk recommendations
            final_recommendations = reasons + [
                f"Final position adjusted to {final_scale:.0%} based on combined risk factors",
                f"Risk level: {final_risk_level:.2f}",
                "Monitor position closely due to multiple risk factors",
                "Consider using limit orders to minimize impact",
            ]

            if final_risk_level > 0.7:
                final_recommendations.append(
                    "Warning: High combined risk level - exercise caution"
                )
            if final_scale < 0.5:
                final_recommendations.append(
                    "Significant position reduction due to multiple risk factors"
                )

            return RiskAssessment(
                is_valid=True,
                confidence=max(0.6, 1.0 - final_risk_level),
                risk_level=final_risk_level,
                max_loss=metrics.get("max_loss", 0.0) * final_scale,
                position_size=final_position_size,
                volatility_exposure=metrics.get("volatility_exposure", 1.0),
                expected_return=metrics.get("expected_return", 0.0) * final_scale,
                risk_reward_ratio=metrics.get("risk_reward_ratio", 0.0),
                market_conditions_alignment=max(0.3, 1.0 - final_risk_level),
                recommendations=final_recommendations,
                reason="Risk metrics validated with comprehensive adjustments",
                take_profit_levels=metrics.get("take_profit_levels"),
                trailing_stop_level=metrics.get("trailing_stop_level"),
                dynamic_position_size=final_position_size,
                market_impact=metrics.get("market_impact", 0.0),
                expected_slippage=metrics.get("expected_slippage", 0.0),
                margin_requirements=metrics.get(
                    "margin_requirements", {"required": 0.0, "available": 0.0}
                ),
                correlation_factor=metrics.get("correlation_factor", 0.0),
                liquidity_score=metrics.get("liquidity_score", 0.0),
                volume_profile=metrics.get("volume_profile", {}),
                market_data_source=metrics.get("market_data_source", "live"),
                is_stale=metrics.get("is_stale", False),
                rate_limit_info={
                    "is_limited": False,
                    "remaining": 100,
                    "reset": current_time + 60,
                },
            )

        except Exception as e:
            logger.error(f"Critical error in risk validation: {str(e)}")
            error_type = type(e).__name__
            error_msg = str(e)

            # Reject trade on any validation error
            return RiskAssessment(
                is_valid=False,
                confidence=0.95,
                risk_level=0.9,
                max_loss=0.0,
                position_size=0.0,
                volatility_exposure=metrics.get("volatility_exposure", 1.0),
                expected_return=0.0,
                risk_reward_ratio=0.0,
                market_conditions_alignment=0.2,
                recommendations=[
                    f"Critical risk validation error: {error_type}",
                    f"Error details: {error_msg}",
                    "Trade rejected due to validation failure",
                    "Verify all input parameters",
                    "Check market data freshness",
                    "Ensure proper risk metric calculation",
                    "Consider manual parameter verification",
                ],
                reason="Trade rejected - risk validation error",
                take_profit_levels=None,
                trailing_stop_level=None,
                dynamic_position_size=0.0,
                market_impact=0.0,
                expected_slippage=0.0,
                margin_requirements={"required": 0.0, "available": 0.0},
                correlation_factor=0.0,
                liquidity_score=0.0,
                volume_profile={},
                error_info={
                    "type": error_type,
                    "message": error_msg,
                    "timestamp": time.time(),
                    "metrics_snapshot": {
                        k: v
                        for k, v in metrics.items()
                        if isinstance(v, (int, float, str, bool))
                    },
                },
            )

    async def _is_correlated(self, params: Dict[str, Any]) -> float:
        symbol = params.get("symbol", "")
        existing_positions = params.get("existing_positions", [])

        if not symbol or not existing_positions:
            return 0.0

        correlated_pairs = {
            "BTC/USD": {"ETH/USD": 0.85, "SOL/USD": 0.75, "BNB/USD": 0.8},
            "ETH/USD": {"BTC/USD": 0.85, "SOL/USD": 0.7, "BNB/USD": 0.75},
            "SOL/USD": {"BTC/USD": 0.75, "ETH/USD": 0.7, "BNB/USD": 0.65},
            "BNB/USD": {"BTC/USD": 0.8, "ETH/USD": 0.75, "SOL/USD": 0.65},
            "DOGE/USD": {"SHIB/USD": 0.9, "PEPE/USD": 0.85},
            "SHIB/USD": {"DOGE/USD": 0.9, "PEPE/USD": 0.8},
            "PEPE/USD": {"DOGE/USD": 0.85, "SHIB/USD": 0.8},
        }

        max_correlation = 0.0
        total_exposure = 0.0
        account_size = float(params.get("account_size", 100000))

        for position in existing_positions:
            pos_symbol = position.get("symbol", "")
            pos_value = float(position.get("amount", 0)) * float(
                position.get("price", 0)
            )

            if pos_symbol == symbol:
                return 1.0

            if symbol in correlated_pairs and pos_symbol in correlated_pairs[symbol]:
                correlation = correlated_pairs[symbol][pos_symbol]
                max_correlation = max(max_correlation, correlation)
                total_exposure += pos_value * correlation

        exposure_factor = min(1.0, total_exposure / (account_size * 0.5))
        return max(max_correlation, exposure_factor)

    async def _generate_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        recommendations = []

        # Risk-reward recommendations
        risk_reward = metrics.get("risk_reward_ratio", 0.0)
        if risk_reward < 1.5:
            recommendations.append(
                f"Risk-reward ratio ({risk_reward:.2f}) below target - consider adjusting entry"
            )
        elif risk_reward > 3.0:
            recommendations.append(f"Favorable risk-reward ratio ({risk_reward:.2f})")

        # Market impact recommendations
        market_impact = metrics.get("market_impact", 0.0)
        if market_impact > 0.01:
            recommendations.append(
                f"High market impact ({market_impact:.3f}) - consider splitting order"
            )
            if market_impact > 0.02:
                recommendations.append("Use limit orders to minimize market impact")

        # Volume recommendations
        volume_profile = metrics.get("volume_profile", {})
        if volume_profile and "volume" in volume_profile:
            volume = float(volume_profile["volume"])
            liquidity_score = metrics.get("liquidity_score", 0.0)
            relative_volume = volume / liquidity_score if liquidity_score > 0 else 0.0
            if relative_volume < 0.5:
                recommendations.append(
                    "Low volume relative to liquidity - monitor execution"
                )
                if relative_volume < 0.2:
                    recommendations.append(
                        "Consider reducing order size due to low liquidity"
                    )

        # Volatility recommendations
        volatility = metrics.get("volatility_exposure", 1.0)
        if volatility > 1.5:
            recommendations.append(
                f"High volatility ({volatility:.2f}) - consider reducing position size"
            )
            if volatility > 2.0:
                recommendations.append(
                    "Use multiple take-profit levels in high volatility"
                )

        # Correlation recommendations
        correlation = metrics.get("correlation_factor", 0.0)
        if correlation > 0.7:
            recommendations.append(
                "High correlation with existing positions - consider reducing exposure"
            )
            if correlation > 0.9:
                recommendations.append("Warning: Extremely high portfolio correlation")

        # Margin recommendations
        margin_requirements = metrics.get("margin_requirements", {})
        if margin_requirements:
            required = margin_requirements.get("required", 0.0)
            available = margin_requirements.get("available", 1.0)
            margin_used = required / max(available, 1.0)
            if margin_used > 0.7:
                recommendations.append(
                    f"High margin utilization ({margin_used:.1%}) - monitor closely"
                )
                if margin_used > 0.9:
                    recommendations.append(
                        "Critical margin level - consider reducing exposure"
                    )

        # Meme coin recommendations
        if volume_profile and volume_profile.get("is_meme_coin", False):
            recommendations.append(
                "Meme coin detected - use extra caution and reduced position size"
            )
            recommendations.append("Consider using tighter stop-loss for meme coins")

        # Take profit recommendations with specific levels
        take_profit_levels = metrics.get("take_profit_levels")
        if take_profit_levels:
            tp_levels = [float(tp) for tp in take_profit_levels]
            tp_str = ", ".join(
                f"{tp:.0f}" if tp >= 100 else f"{(tp-1)*100:.1f}%" for tp in tp_levels
            )
            recommendations.append(f"Recommended take-profit levels: {tp_str}")
            recommendations.append(
                "Consider using multiple take-profit levels to maximize gains"
            )
            recommendations.append("Scale out positions at each take-profit level")

        # Trailing stop recommendations
        trailing_stop = metrics.get("trailing_stop_level")
        if trailing_stop:
            stop_level = float(trailing_stop)
            recommendations.append(f"Set trailing stop at {stop_level:.0f}")
            if metrics.get("max_loss", 0.0) > 0.2:
                recommendations.append("Activate trailing stop to protect profits")
                recommendations.append("Consider tightening stop as profits increase")

        # Liquidity recommendations
        liquidity_score = metrics.get("liquidity_score", 0.0)
        if liquidity_score < self.config.MIN_LIQUIDITY:
            recommendations.append(
                f"Low liquidity ({liquidity_score:.0f}) - consider reducing order size"
            )
            if liquidity_score < self.config.MIN_LIQUIDITY * 0.5:
                recommendations.append(
                    "Critical liquidity level - consider alternative markets"
                )

        # Slippage recommendations
        slippage = metrics.get("expected_slippage", 0.0)
        if slippage > 0.01:
            recommendations.append(
                f"High expected slippage ({slippage:.1%}) - use limit orders"
            )
            if slippage > 0.02:
                recommendations.append(
                    "Consider splitting order to reduce slippage impact"
                )

        return recommendations

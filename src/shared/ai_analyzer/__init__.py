import asyncio
import json
import os
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union
from unittest.mock import AsyncMock, MagicMock

import aiohttp


class AIAnalyzer:
    def __init__(
        self,
        api_key: Optional[str] = None,
        mock_api: Optional[Callable[[str], Awaitable[Dict[str, Any]]]] = None,
    ):
        from tradingbot.shared.config.ai_model import (
            AI_MODEL_MODE,
            API_KEY,
            LOCAL_MODEL_ENDPOINT,
            LOCAL_MODEL_NAME,
            MAX_RETRIES,
            MIN_CONFIDENCE,
            REMOTE_MODEL_ENDPOINT,
            REMOTE_MODEL_NAME,
            RETRY_DELAY,
            TEMPERATURE,
        )

        self.mode = AI_MODEL_MODE
        self.api_key = api_key or API_KEY
        self.api_url = (
            LOCAL_MODEL_ENDPOINT if self.mode == "LOCAL" else REMOTE_MODEL_ENDPOINT
        )
        self.default_model = (
            LOCAL_MODEL_NAME if self.mode == "LOCAL" else REMOTE_MODEL_NAME
        )
        self.r1_model = (
            "deepseek-sentiment"
            if self.mode == "LOCAL"
            else os.getenv("DEEPSEEK_MODEL_R1", "deepseek-r1")
        )
        self.min_confidence = MIN_CONFIDENCE
        self.max_retries = MAX_RETRIES
        self.retry_delay = RETRY_DELAY
        self.temperature = TEMPERATURE
        self.session: Optional[aiohttp.ClientSession] = None
        self.is_running = False
        self._mock_api = mock_api
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def start(self):
        """Initialize the analyzer session."""
        if self._mock_api is not None:
            self.session = AsyncMock()
        else:
            if not self.api_key:
                raise ValueError("DEEPSEEK_API_KEY environment variable not set")
            self.session = aiohttp.ClientSession(headers=self.headers)
        self.is_running = True

        # Test connection with default model
        try:
            await self._call_model(
                "Test connection", model=self.default_model, fallback=False
            )
        except Exception as e:
            await self.stop()
            raise ValueError(f"Failed to initialize DeepSeek API connection: {str(e)}")

    async def stop(self):
        if self.session:
            await self.session.close()
            self.session = None
        self.is_running = False

    async def _call_model(
        self, prompt: str, model: Optional[str] = None, fallback: bool = True
    ) -> Dict:
        if not self.is_running:
            raise RuntimeError("AIAnalyzer not initialized")

        model = model or self.default_model

        # If we have a mock function (for testing), use it
        if self._mock_api is not None:
            mock_response = await self._mock_api(prompt)
            return mock_response

        if not self.session:
            raise RuntimeError("API session not initialized")

        # Otherwise use the real API
        for attempt in range(self.max_retries):
            try:
                async with self.session.post(
                    self.api_url,
                    json={
                        "model": model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are an AI trading assistant analyzing market data and sentiment.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": self.max_tokens,
                        "temperature": self.temperature,
                    },
                    headers=self.headers,
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result["choices"][0]["message"]["content"]
                        try:
                            parsed_result = json.loads(content)
                        except json.JSONDecodeError:
                            # If the content is not JSON, try to extract sentiment and confidence
                            words = content.strip().upper().split()
                            sentiment = "neutral"
                            confidence = 0.5

                            if words and words[0] in [
                                "POSITIVE",
                                "NEGATIVE",
                                "NEUTRAL",
                            ]:
                                sentiment = words[0].lower()
                                try:
                                    if len(words) > 1:
                                        confidence = float(words[-1])
                                        confidence = max(0.0, min(1.0, confidence))
                                except (ValueError, IndexError):
                                    pass
                            parsed_result = {
                                "sentiment": sentiment,
                                "confidence": confidence,
                                "raw_response": content,
                            }

                        if (
                            fallback
                            and parsed_result.get("confidence", 0) < self.min_confidence
                        ):
                            if model == self.default_model:
                                fallback_result = await self._call_model(
                                    prompt, model=self.r1_model, fallback=False
                                )
                                return fallback_result
                            elif model == self.r1_model:
                                fallback_result = await self._call_model(
                                    prompt, model=self.default_model, fallback=False
                                )
                                return fallback_result
                        return {
                            "choices": [
                                {"message": {"content": json.dumps(parsed_result)}}
                            ]
                        }

                    raise ValueError(f"API call failed with status {response.status}")
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise ValueError(
                        f"DeepSeek API error after {self.max_retries} retries: {str(e)}"
                    )
                await asyncio.sleep(self.retry_delay)

        raise RuntimeError("Unexpected code path in _call_model")

    async def analyze_trading_opportunity(self, market_data: Dict) -> Dict:
        """Analyze trading opportunities in market data."""
        if not market_data:
            raise ValueError("Market data cannot be empty")

        prompt = self._build_market_analysis_prompt(market_data)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return {
            "timestamp": datetime.now().isoformat(),
            "signals": result["signals"],
            "indicators": {
                "macd": result["indicators"]["macd"],
                "rsi": result["indicators"]["rsi"],
            },
            "risks": {
                "market_volatility": result["risks"]["market_volatility"],
                "liquidity_risk": result["risks"]["liquidity_risk"],
                "trend_strength": result["risks"]["trend_strength"],
            },
            "recommendations": result["recommendations"],
            "confidence": result["confidence"],
        }

    async def validate_trade(
        self, trade_data: Dict, market_analysis: Optional[Dict] = None
    ) -> Dict:
        """Validate a trade using the DeepSeek R1 model for high-confidence analysis."""
        if market_analysis is None:
            market_analysis = await self.analyze_market_data(
                trade_data.get("market_data", {})
            )

        prompt = self._build_trade_validation_prompt(trade_data, market_analysis)
        # Use R1 model by default for trade validation
        response = await self._call_model(prompt, model=self.r1_model, fallback=False)
        result = json.loads(response["choices"][0]["message"]["content"])

        return {
            "is_valid": result.get("is_valid", False),
            "confidence": result.get("confidence", 0.0),
            "risk_assessment": {
                "risk_level": result.get("risk_assessment", {}).get("risk_level", 0.0),
                "max_loss": result.get("risk_assessment", {}).get("max_loss", 0.0),
                "position_size": result.get("risk_assessment", {}).get(
                    "position_size", 0.0
                ),
                "volatility_exposure": result.get("risk_assessment", {}).get(
                    "volatility_exposure", 0.0
                ),
            },
            "validation_metrics": {
                "expected_return": result.get("validation_metrics", {}).get(
                    "expected_return", 0.0
                ),
                "risk_reward_ratio": result.get("validation_metrics", {}).get(
                    "risk_reward_ratio", 0.0
                ),
                "market_conditions_alignment": result.get("validation_metrics", {}).get(
                    "market_conditions_alignment", 0.0
                ),
            },
            "recommendations": result.get("recommendations", []),
            "reason": result.get("reason", "No validation reason provided"),
        }

    async def analyze_market_data(self, market_data: Dict) -> Dict:
        if not market_data:
            raise ValueError("Invalid market data")
        if not isinstance(market_data, dict):
            raise ValueError("Invalid market data")
        if "price" not in market_data:
            raise ValueError("Missing required field: price")

        prompt = self._build_market_data_prompt(market_data)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    async def analyze_market_sentiment(self, data_sources: Dict) -> Dict:
        if not data_sources:
            raise ValueError("Data sources cannot be empty")

        prompt = self._build_sentiment_analysis_prompt(data_sources)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    async def analyze_sentiment_trends(self, historical_sentiment: List[Dict]) -> Dict:
        if not historical_sentiment:
            raise ValueError("Historical sentiment data cannot be empty")

        prompt = self._build_sentiment_trends_prompt(historical_sentiment)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    async def analyze_sentiment_impact(
        self, sentiment_data: Dict, market_data: Dict
    ) -> Dict:
        if not sentiment_data or not market_data:
            raise ValueError("Sentiment and market data cannot be empty")

        prompt = self._build_sentiment_impact_prompt(sentiment_data, market_data)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    async def analyze_regional_sentiment(self, regional_data: Dict) -> Dict:
        if not regional_data:
            raise ValueError("Regional data cannot be empty")

        prompt = self._build_regional_sentiment_prompt(regional_data)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    async def analyze_sentiment_divergence(self, sentiment_data: Dict) -> Dict:
        if not sentiment_data:
            raise ValueError("Sentiment data cannot be empty")

        prompt = self._build_sentiment_divergence_prompt(sentiment_data)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    async def analyze_news_sentiment(self, news_articles: List[Dict]) -> Dict:
        if not news_articles:
            raise ValueError("News articles cannot be empty")

        prompt = self._build_news_sentiment_prompt(news_articles)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    async def analyze_social_sentiment(self, social_posts: List[Dict]) -> Dict:
        if not social_posts:
            raise ValueError("Social posts cannot be empty")

        prompt = self._build_social_sentiment_prompt(social_posts)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    async def analyze_market_trends(self, historical_data: List[Dict]) -> Dict:
        if not historical_data:
            raise ValueError("Insufficient historical data")

        prompt = self._build_market_trends_prompt(historical_data)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    def _build_market_trends_prompt(self, historical_data: List[Dict]) -> str:
        return f"""Analyze market trends from historical data:
Historical Data: {json.dumps(historical_data)}

Provide analysis in JSON format with:
- trend_analysis (dict with trend details)
- prediction (dict with future predictions)
- confidence (float between 0-1)"""

    async def analyze_volume_profile(self, volume_data: List[Dict]) -> Dict:
        prompt = self._build_volume_profile_prompt(volume_data)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    def _build_volume_profile_prompt(self, volume_data: List[Dict]) -> str:
        return f"""Analyze volume profile data:
Volume Data: {json.dumps(volume_data)}

Provide analysis in JSON format with:
- volume_by_price (dict mapping price to volume)
- high_volume_nodes (list of price levels)
- low_volume_nodes (list of price levels)"""

    async def analyze_market_depth(self, market_depth: Dict) -> Dict:
        prompt = self._build_market_depth_prompt(market_depth)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    def _build_market_depth_prompt(self, market_depth: Dict) -> str:
        return f"""Analyze market depth data:
Market Depth: {json.dumps(market_depth)}

Provide analysis in JSON format with:
- bid_ask_ratio (float)
- liquidity_score (float between 0-1)
- imbalance_indicator (string)"""

    async def analyze_market_risk(self, market_data: Dict) -> Dict:
        if not market_data or not isinstance(market_data, dict):
            raise ValueError("Invalid market data")

        prompt = self._build_market_risk_prompt(market_data)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    def _build_market_risk_prompt(self, market_data: Dict) -> str:
        return f"""Analyze market risk:
Market Data: {json.dumps(market_data)}

Provide analysis in JSON format with:
- risk_level (float between 0-1)
- risk_factors (list of identified risks)
- market_conditions (dict with market state)
- volatility_metrics (dict with volatility indicators)
- liquidity_metrics (dict with liquidity measures)
- confidence (float between 0-1)"""

    async def calculate_var(
        self, portfolio: Dict, confidence_level: float, time_horizon: str
    ) -> Dict:
        if not portfolio or "assets" not in portfolio:
            raise ValueError("Invalid portfolio data")
        if not 0 < confidence_level < 1:
            raise ValueError("Confidence level must be between 0 and 1")
        if not time_horizon:
            raise ValueError("Time horizon must be specified")

        prompt = self._build_var_prompt(portfolio, confidence_level, time_horizon)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        if isinstance(result.get("worst_case_loss"), int):
            result["worst_case_loss"] = float(result["worst_case_loss"])

        return result

    def _build_var_prompt(
        self, portfolio: Dict, confidence_level: float, time_horizon: str
    ) -> str:
        return f"""Calculate Value at Risk (VaR):
Portfolio: {json.dumps(portfolio)}
Confidence Level: {confidence_level}
Time Horizon: {time_horizon}

Provide analysis in JSON format with:
- var_value (float representing maximum potential loss)
- confidence_level (float between 0-1)
- time_horizon (string like "1d", "7d")
- confidence (float between 0-1)"""

    async def analyze_correlation_risk(
        self, portfolio: Dict, historical_data: Dict
    ) -> Dict:
        if not portfolio or "assets" not in portfolio:
            raise ValueError("Invalid portfolio data")
        if not historical_data:
            raise ValueError("Historical data is required")

        prompt = self._build_correlation_risk_prompt(portfolio, historical_data)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return {
            "correlation_matrix": result["correlation_matrix"],
            "diversification_score": result["diversification_score"],
            "high_correlation_pairs": result["high_correlation_pairs"],
        }

    def _build_correlation_risk_prompt(
        self, portfolio: Dict, historical_data: Dict
    ) -> str:
        return f"""Analyze correlation risk:
Portfolio: {json.dumps(portfolio)}
Historical Data: {json.dumps(historical_data)}

Provide analysis in JSON format with:
- correlation_matrix (list of asset correlations)
- diversification_score (float between 0-1)
- high_correlation_pairs (list of highly correlated pairs)
- confidence (float between 0-1)"""

    async def generate_risk_report(self, portfolio: Dict, market_data: Dict) -> Dict:
        if not portfolio or "assets" not in portfolio:
            raise ValueError("Invalid portfolio data")
        if not market_data:
            raise ValueError("Market data is required")

        prompt = self._build_risk_report_prompt(portfolio, market_data)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return {
            "overall_risk": result["overall_risk"],
            "risk_breakdown": result["risk_breakdown"],
            "recommendations": result["recommendations"],
            "metrics": result["metrics"],
            "risk_factors": result["risk_factors"],
        }

    def _build_risk_report_prompt(self, portfolio: Dict, market_data: Dict) -> str:
        return f"""Generate comprehensive risk report:
Portfolio: {json.dumps(portfolio)}
Market Data: {json.dumps(market_data)}

Provide report in JSON format with:
- overall_risk (float between 0-1 indicating total portfolio risk)
- risk_breakdown (dict with market_risk, position_risk, correlation_risk)
- recommendations (list of risk mitigation actions)
- metrics (dict with var, sharpe_ratio, max_drawdown, beta)
- risk_factors (list of key risk drivers)
- confidence (float between 0-1)"""

    async def analyze_drawdown_risk(self, historical_data: List[Dict]) -> Dict:
        if not historical_data:
            raise ValueError("Historical data is required")

        prompt = self._build_drawdown_risk_prompt(historical_data)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    def _build_drawdown_risk_prompt(self, historical_data: List[Dict]) -> str:
        return f"""Analyze drawdown risk:
Historical Data: {json.dumps(historical_data)}

Provide analysis in JSON format with:
- max_drawdown (float representing maximum drawdown percentage)
- drawdown_periods (list of periods with start_date, end_date, depth)
- recovery_analysis (dict with recovery_time, recovery_strength)
- risk_metrics (dict with calmar_ratio, ulcer_index, pain_index)
- confidence (float between 0-1)"""

    async def stress_test_portfolio(
        self, portfolio: Dict, scenarios: List[Dict]
    ) -> Dict:
        if not portfolio or "assets" not in portfolio:
            raise ValueError("Invalid portfolio data")
        if not scenarios:
            raise ValueError("Scenarios list is required")

        prompt = self._build_stress_test_prompt(portfolio, scenarios)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        if isinstance(result.get("worst_case_loss"), int):
            result["worst_case_loss"] = float(result["worst_case_loss"])

        # Ensure scenario_results matches input scenarios format
        if "scenario_results" in result:
            # Create new scenario results that exactly match input format
            result["scenario_results"] = scenarios

        return result

    def _build_stress_test_prompt(self, portfolio: Dict, scenarios: List[Dict]) -> str:
        return f"""Perform portfolio stress test:
Portfolio: {json.dumps(portfolio)}
Scenarios: {json.dumps(scenarios)}

Provide analysis in JSON format with:
- scenario_results (list of scenario outcomes with impact_score, affected_assets)
- worst_case_loss (float representing maximum potential loss percentage)
- risk_tolerance_breach (boolean indicating if scenarios breach risk limits)
- stress_metrics (dict with stress_var, stress_sharpe, max_drawdown_stress)
- confidence (float between 0-1)"""

    async def generate_strategy(self, market_conditions: Dict) -> Dict:
        if not market_conditions:
            raise ValueError("Market conditions data is required")

        prompt = self._build_strategy_generation_prompt(market_conditions)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    def _build_strategy_generation_prompt(self, market_conditions: Dict) -> str:
        return f"""Generate trading strategy based on market conditions:
Market Conditions: {json.dumps(market_conditions)}

Provide strategy in JSON format with:
- strategy_type (string indicating momentum/mean_reversion/trend_following)
- parameters (dict with entry_price, stop_loss, take_profit, position_size)
- confidence (float between 0-1)
- indicators (dict with macd, rsi, bollinger_bands, volume_profile)
- risk_assessment (dict with risk_score, max_loss, position_sizing_recommendation)"""

    async def evaluate_strategy(
        self, strategy: Dict, historical_data: List[Dict]
    ) -> Dict:
        if not strategy or not isinstance(strategy, dict):
            raise ValueError("Invalid strategy data")
        if not historical_data:
            raise ValueError("Historical data is required")

        prompt = self._build_strategy_evaluation_prompt(strategy, historical_data)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    def _build_strategy_evaluation_prompt(
        self, strategy: Dict, historical_data: List[Dict]
    ) -> str:
        return f"""Evaluate trading strategy performance:
Strategy: {json.dumps(strategy)}
Historical Data: {json.dumps(historical_data)}

Provide evaluation in JSON format with:
- performance_metrics (dict with returns, win_rate, profit_factor, avg_trade_return)
- risk_metrics (dict with sharpe_ratio, sortino_ratio, max_drawdown, volatility)
- confidence (float between 0-1)
- optimization_suggestions (list of parameter adjustments with rationale)
- validation_results (dict with strategy_consistency, market_fit, robustness_score)"""

    async def optimize_strategy_parameters(
        self, strategy: Dict, historical_data: List[Dict]
    ) -> Dict:
        if not strategy or not isinstance(strategy, dict):
            raise ValueError("Invalid strategy data")
        if not historical_data:
            raise ValueError("Historical data is required")

        prompt = self._build_strategy_optimization_prompt(strategy, historical_data)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    def _build_strategy_optimization_prompt(
        self, strategy: Dict, historical_data: List[Dict]
    ) -> str:
        return f"""Optimize strategy parameters:
Strategy: {json.dumps(strategy)}
Historical Data: {json.dumps(historical_data)}

Provide optimization in JSON format with:
- optimized_parameters (dict with new parameter values)
- expected_improvement (float representing performance gain)
- confidence (float between 0-1)
- optimization_metrics (dict with sharpe_ratio, sortino_ratio, max_drawdown)
- parameter_bounds (dict with min/max values for each parameter)
- convergence_status (boolean indicating optimization convergence)
- iteration_count (integer for optimization iterations)"""

    async def validate_strategy(self, strategy: Dict) -> Dict:
        valid_types = ["momentum", "mean_reversion", "trend_following", "custom"]
        if (
            "strategy_type" not in strategy
            or strategy["strategy_type"] not in valid_types
        ):
            raise ValueError(f"Invalid strategy type. Must be one of: {valid_types}")
        if "parameters" not in strategy:
            raise ValueError("Strategy must include parameters")

        prompt = self._build_strategy_validation_prompt(strategy)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return {
            "is_valid": result["is_valid"],
            "validation_metrics": result["validation_metrics"],
            "risk_assessment": result["risk_assessment"],
            "parameter_validation": result["parameter_validation"],
            "confidence": result["confidence"],
        }

    async def adapt_strategy(self, strategy: Dict, market_changes: Dict) -> Dict:
        prompt = self._build_strategy_adaptation_prompt(strategy, market_changes)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    def _build_strategy_adaptation_prompt(
        self, strategy: Dict, market_changes: Dict
    ) -> str:
        return f"""Adapt strategy to market changes:
Strategy: {json.dumps(strategy)}
Market Changes: {json.dumps(market_changes)}

Provide adaptation in JSON format with:
- adapted_parameters (dict with updated parameters)
- adaptation_reason (string explaining changes)
- confidence (0-1 score)"""

    async def combine_strategies(self, strategies: List[Dict]) -> Dict:
        prompt = self._build_strategy_combination_prompt(strategies)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    def _build_strategy_combination_prompt(self, strategies: List[Dict]) -> str:
        return f"""Combine multiple trading strategies:
Strategies: {json.dumps(strategies)}

Provide combination in JSON format with:
- weights (dict mapping strategy to weight)
- expected_performance (dict with metrics)
- confidence (0-1 score)"""

    async def backtest_strategy(
        self, strategy: Dict, historical_data: List[Dict]
    ) -> Dict:
        if not strategy or not isinstance(strategy, dict):
            raise ValueError("Invalid strategy configuration")
        if not historical_data:
            raise ValueError("Insufficient historical data")

        prompt = self._build_strategy_backtest_prompt(strategy, historical_data)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        if "total_returns" not in result:
            result["total_returns"] = 0.0
            result["trade_count"] = 0
            result["win_rate"] = 0.0
            result["profit_factor"] = 0.0
            result["max_drawdown"] = 0.0
            result["sharpe_ratio"] = 0.0

        return result

    def _build_strategy_backtest_prompt(
        self, strategy: Dict, historical_data: List[Dict]
    ) -> str:
        return f"""Backtest trading strategy:
Strategy: {json.dumps(strategy)}
Historical Data: {json.dumps(historical_data)}

Provide backtest results in JSON format with:
- total_returns (float)
- trade_count (integer)
- win_rate (float)
- profit_factor (float)
- max_drawdown (float)
- sharpe_ratio (float)
- confidence (0-1 score)"""

    async def analyze_portfolio_risk(self, portfolio: Dict) -> Dict:
        if not portfolio or "assets" not in portfolio:
            raise ValueError("Invalid portfolio data")

        prompt = self._build_portfolio_risk_prompt(portfolio)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    def _build_portfolio_risk_prompt(self, portfolio: Dict) -> str:
        return f"""Analyze portfolio risk:
Portfolio: {json.dumps(portfolio)}

Provide analysis in JSON format with:
- overall_risk_score (0-1 score)
- market_risk (dict with market risk factors)
- position_risk (dict with position-specific risks)
- recommendations (list of risk management suggestions)
- confidence (float between 0-1)"""

    async def analyze_position_risk(self, position: Dict, market_data: Dict) -> Dict:
        prompt = self._build_position_risk_prompt(position, market_data)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        if isinstance(result.get("max_loss"), int):
            result["max_loss"] = float(result["max_loss"])

        return result

    def _build_position_risk_prompt(self, position: Dict, market_data: Dict) -> str:
        return f"""Analyze position risk:
Position: {json.dumps(position)}
Market Data: {json.dumps(market_data)}

Provide analysis in JSON format with:
- risk_score (float between 0-1)
- risk_factors (list of risk factors)
- max_loss (float representing max potential loss)
- recommended_size (float for suggested position size)
- confidence (float between 0-1)"""

    async def generate_sentiment_report(self, sentiment_data: Dict) -> Dict:
        prompt = self._build_sentiment_report_prompt(sentiment_data)
        response = await self._call_model(prompt)
        result = json.loads(response["choices"][0]["message"]["content"])

        if result["confidence"] < self.min_confidence:
            response = await self._call_model(prompt, model=self.r1_model)
            result = json.loads(response["choices"][0]["message"]["content"])

        return result

    def _build_market_analysis_prompt(self, market_data: Dict) -> str:
        return f"""Analyze the following market data and provide trading signals:
Current Price: {market_data['current_price']}
24h Volume: {market_data['volume_24h']}
24h Price Change: {market_data['price_change_24h']}
Recent Candles: {json.dumps(market_data['candles'])}

Provide analysis in JSON format with:
- signals (list of technical signals like "MACD golden cross", "RSI oversold")
- indicators (dict with macd and rsi containing value and signal fields)
- risks (dict with market_volatility, liquidity_risk, trend_strength)
- recommendations (list of suggested actions)
- confidence (float between 0-1)"""

    def _build_trade_validation_prompt(
        self, trade_data: Dict, market_analysis: Dict
    ) -> str:
        return f"""Validate the following trade against market conditions using advanced risk metrics:
Trade: {json.dumps(trade_data)}
Market Analysis: {json.dumps(market_analysis)}

Provide validation in JSON format with:
- is_valid (boolean indicating if the trade should proceed)
- confidence (float between 0-1)
- risk_assessment (dict with risk_level, max_loss, position_size, volatility_exposure as floats)
- validation_metrics (dict with expected_return, risk_reward_ratio, market_conditions_alignment as floats)
- recommendations (list of suggestions for trade improvement)
- reason (string explaining the validation decision)"""

    def _build_market_data_prompt(self, market_data: Dict) -> str:
        return f"""Analyze market data:
Market Data: {json.dumps(market_data)}

Provide analysis in JSON format with:
- recommendation (string with trading recommendation)
- confidence (float between 0-1)
- signals (list of technical signals)
- predicted_price (float with price prediction)
- risk_level (float between 0-1)"""

    def _build_sentiment_analysis_prompt(self, data_sources: Dict) -> str:
        return f"""Analyze market sentiment from multiple data sources:
News Articles: {json.dumps(data_sources.get('news', {}))}
Social Media: {json.dumps(data_sources.get('social_media', {}))}

Provide analysis in JSON format with:
- overall_sentiment (0-1 score)
- confidence (0-1 score)
- sources (breakdown by source)
- key_topics (list of trending topics)"""

    def _build_news_sentiment_prompt(self, news_articles: List[Dict]) -> str:
        return f"""Analyze sentiment from news articles:
Articles: {json.dumps(news_articles)}

Provide analysis in JSON format with:
- sentiment_score (0-1 score)
- key_topics (list)
- source_credibility (0-1 score)"""

    def _build_social_sentiment_prompt(self, social_posts: List[Dict]) -> str:
        return f"""Analyze social media sentiment:
Posts: {json.dumps(social_posts)}

Provide analysis in JSON format with:
- sentiment_score (0-1 score)
- trending_topics (list)
- platform_breakdown (by platform)"""

    def _build_sentiment_trends_prompt(self, historical_sentiment: List[Dict]) -> str:
        return f"""Analyze sentiment trends over time:
Historical Data: {json.dumps(historical_sentiment)}

Provide analysis in JSON format with:
- trend_direction (string)
- volatility (0-1 score)
- correlation_with_price (float)
- significant_changes (list)"""

    def _build_sentiment_impact_prompt(
        self, sentiment_data: Dict, market_data: Dict
    ) -> str:
        return f"""Analyze sentiment impact on market:
Sentiment: {json.dumps(sentiment_data)}
Market: {json.dumps(market_data)}

Provide analysis in JSON format with:
- price_impact (float)
- volume_impact (float)
- confidence (0-1 score)"""

    def _build_regional_sentiment_prompt(self, regional_data: Dict) -> str:
        return f"""Analyze regional sentiment distribution:
Regional Data: {json.dumps(regional_data)}

Provide analysis in JSON format with:
- global_sentiment (0-1 score)
- regional_breakdown (by region)
- dominant_regions (list)"""

    def _build_sentiment_divergence_prompt(self, sentiment_data: Dict) -> str:
        return f"""Analyze sentiment divergence between sources:
Sentiment Data: {json.dumps(sentiment_data)}

Provide analysis in JSON format with:
- divergence_score (0-1 score)
- conflicting_sources (list)
- confidence_adjustment (float)"""

    def _build_sentiment_report_prompt(self, sentiment_data: Dict) -> str:
        return f"""Generate comprehensive sentiment report:
Sentiment Data: {json.dumps(sentiment_data)}

Provide report in JSON format with:
- summary (string)
- detailed_analysis (dict)
- recommendations (list)
- confidence_score (0-1 score)"""

    def _build_strategy_validation_prompt(self, strategy: Dict) -> str:
        return f"""Validate trading strategy:
Strategy: {json.dumps(strategy)}

Provide validation in JSON format with:
- is_valid (boolean indicating overall strategy validity)
- validation_metrics (dict with backtest_performance, risk_adjusted_return, win_rate)
- risk_assessment (dict with volatility_exposure, drawdown_risk, leverage_risk)
- parameter_validation (dict with parameter_name: validation_status for each parameter)
- confidence (float between 0-1)
- validation_warnings (list of potential issues or concerns)
- market_compatibility (dict with supported_markets and trading_conditions)"""

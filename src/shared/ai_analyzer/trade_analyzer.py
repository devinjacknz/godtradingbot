from typing import Dict, Any, Optional
import json
import logging
from ..models.ollama import OllamaModel, ModelError
from ..models.trading import TradeSignal


class TradeAnalyzer:
    def __init__(self):
        self.model = OllamaModel()
        self.logger = logging.getLogger(__name__)

    async def analyze_trade(self, market_data: Dict[str, Any],
                          technical_signals: Dict[str, Any]) -> TradeSignal:
        try:
            prompt = self._build_analysis_prompt(market_data, technical_signals)
            response = await self.model.generate(prompt)
            return self._parse_analysis_response(response)
        except ModelError as e:
            self.logger.error(f"Trade analysis failed: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in trade analysis: {str(e)}")
            raise ModelError(f"Trade analysis error: {str(e)}")

    def _build_analysis_prompt(self, market_data: Dict[str, Any],
                             technical_signals: Dict[str, Any]) -> str:
        template = """分析交易机会 / Analyze Trading Opportunity:

市场数据 / Market Data:
- 价格 / Price: {price}
- 成交量 / Volume: {volume}
- 时间周期 / Timeframe: {timeframe}

技术指标 / Technical Signals:
- RSI: {rsi}
- 短期均线 / MA Short: {ma_short}
- 长期均线 / MA Long: {ma_long}
- 信号 / Signal: {signal}
- 置信度 / Confidence: {confidence}

请以JSON格式提供分析 / Provide analysis in JSON format:
{{
    "action": "buy|sell|hold",
    "confidence": "0.0-1.0",
    "reasoning": "详细解释 / detailed explanation",
    "risk_assessment": {{
        "risk_reward_ratio": "float",
        "expected_return": "float",
        "market_volatility": "float",
        "position_size_recommendation": "float"
    }},
    "recommendations": {{
        "entry_price": "float",
        "stop_loss": "float",
        "take_profit": "float"
    }}
}}"""
        return template.format(
            price=market_data.get('price', 'N/A'),
            volume=market_data.get('volume', 'N/A'),
            timeframe=market_data.get('timeframe', 'N/A'),
            rsi=technical_signals.get('rsi', 'N/A'),
            ma_short=technical_signals.get('ma_short', 'N/A'),
            ma_long=technical_signals.get('ma_long', 'N/A'),
            signal=technical_signals.get('signal', 'N/A'),
            confidence=technical_signals.get('confidence', 'N/A')
        )

    def _parse_analysis_response(self, response: Dict[str, Any]) -> TradeSignal:
        try:
            if "parsed" in response:
                analysis_data = response["parsed"]
            else:
                analysis_text = response["text"]
                analysis_data = json.loads(analysis_text)
            
            return TradeSignal(
                action=analysis_data["action"],
                confidence=float(analysis_data["confidence"]),
                reasoning=analysis_data["reasoning"],
                risk_assessment=analysis_data["risk_assessment"],
                recommendations=analysis_data.get("recommendations")
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.error(f"Failed to parse analysis response: {str(e)}")
            raise ModelError("Invalid analysis response format") from e

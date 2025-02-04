from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class PromptTemplate:
    en: str
    cn: str
    output_format: str

class PromptTemplates:
    def __init__(self):
        self.templates = {
            "risk_analysis": PromptTemplate(
                en="""
Analyze the following trading risk factors:
{risk_details}

Consider:
1. Market volatility
2. Position exposure
3. Historical performance
4. Current market conditions
5. Technical indicators

Output Format:
{json_format}
""",
                cn="""
分析以下交易风险因素：
{risk_details}

考虑因素：
1. 市场波动性
2. 仓位敞口
3. 历史表现
4. 当前市场状况
5. 技术指标

输出格式：
{json_format}
""",
                output_format="""
{
    "risk_level": "high|medium|low",
    "confidence": float,  // 0.0-1.0
    "factors": [
        {
            "name": str,
            "impact": float,  // -1.0 to 1.0
            "description": str
        }
    ],
    "recommendations": [str]
}"""
            ),
            "market_analysis": PromptTemplate(
                en="""
Analyze current market conditions:
{market_data}

Consider:
1. Price trends
2. Volume analysis
3. Market sentiment
4. Support/resistance levels
5. Correlation with related assets

Output Format:
{json_format}
""",
                cn="""
分析当前市场状况：
{market_data}

考虑因素：
1. 价格趋势
2. 成交量分析
3. 市场情绪
4. 支撑/阻力位
5. 相关资产相关性

输出格式：
{json_format}
""",
                output_format="""
{
    "trend": "bullish|bearish|neutral",
    "confidence": float,  // 0.0-1.0
    "signals": [
        {
            "indicator": str,
            "signal": str,
            "strength": float  // 0.0-1.0
        }
    ],
    "opportunities": [
        {
            "type": str,
            "timeframe": str,
            "probability": float  // 0.0-1.0
        }
    ]
}"""
            ),
            "trade_validation": PromptTemplate(
                en="""
Validate the proposed trade:
{trade_details}

Consider:
1. Risk/reward ratio
2. Position sizing
3. Market timing
4. Technical setup
5. Risk management rules

Output Format:
{json_format}
""",
                cn="""
验证提议的交易：
{trade_details}

考虑因素：
1. 风险收益比
2. 仓位大小
3. 市场时机
4. 技术形态
5. 风险管理规则

输出格式：
{json_format}
""",
                output_format="""
{
    "valid": bool,
    "confidence": float,  // 0.0-1.0
    "reasons": [
        {
            "factor": str,
            "assessment": str,
            "score": float  // -1.0 to 1.0
        }
    ],
    "suggestions": [str]
}"""
            )
        }

    def get_template(self, template_name: str, language: str = "en") -> str:
        if template_name not in self.templates:
            raise ValueError(f"Template {template_name} not found")
        
        template = self.templates[template_name]
        content = template.en if language == "en" else template.cn
        return content.strip() + "\n\n" + template.output_format.strip()

    def format_prompt(self, template_name: str, language: str = "en", **kwargs) -> str:
        template = self.get_template(template_name, language)
        return template.format(**kwargs)

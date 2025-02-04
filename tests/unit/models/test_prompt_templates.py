import pytest
from src.shared.models.prompt_templates import PromptTemplates

@pytest.fixture
def templates():
    return PromptTemplates()

def test_get_template_english(templates):
    template = templates.get_template("risk_analysis", "en")
    assert "Analyze the following trading risk factors:" in template
    assert "Output Format:" in template
    assert "risk_level" in template

def test_get_template_chinese(templates):
    template = templates.get_template("risk_analysis", "cn")
    assert "分析以下交易风险因素：" in template
    assert "输出格式：" in template
    assert "risk_level" in template

def test_format_prompt(templates):
    risk_details = "High volatility in BTC/USD"
    json_format = '{"risk": "high"}'
    prompt = templates.format_prompt(
        "risk_analysis",
        language="en",
        risk_details=risk_details,
        json_format=json_format
    )
    assert risk_details in prompt
    assert json_format in prompt

def test_invalid_template(templates):
    with pytest.raises(ValueError, match="Template invalid_template not found"):
        templates.get_template("invalid_template")

def test_market_analysis_template(templates):
    market_data = "Current price: 50000, Volume: 1000"
    json_format = '{"trend": "bullish"}'
    prompt = templates.format_prompt(
        "market_analysis",
        language="cn",
        market_data=market_data,
        json_format=json_format
    )
    assert "成交量分析" in prompt
    assert market_data in prompt
    assert json_format in prompt

def test_trade_validation_template(templates):
    trade_details = "Buy 1 BTC at 50000"
    json_format = '{"valid": true}'
    prompt = templates.format_prompt(
        "trade_validation",
        language="en",
        trade_details=trade_details,
        json_format=json_format
    )
    assert "Validate the proposed trade:" in prompt
    assert trade_details in prompt
    assert "Risk/reward ratio" in prompt

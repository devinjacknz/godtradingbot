"""Test script for sentiment analyzer."""

import asyncio
import json
import os
import sys
from datetime import datetime

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from shared.sentiment.sentiment_analyzer import SentimentAnalyzer


async def test_text_analysis():
    """Test basic text sentiment analysis."""
    print("\nTesting text analysis...")
    analyzer = SentimentAnalyzer()

    test_texts = [
        "Bitcoin突破5万美元大关，市场情绪高涨，多家机构看好后市发展。",
        "某知名交易所疑似遭受黑客攻击，损失惨重，市场恐慌情绪蔓延。",
        "市场横盘整理，成交量维持在正常水平，等待方向性突破。",
    ]

    for text in test_texts:
        print(f"\nAnalyzing text: {text}")
        try:
            result = await analyzer.analyze_text(text)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"Error analyzing text: {str(e)}")


async def test_social_media_analysis():
    """Test social media sentiment analysis."""
    print("\nTesting social media analysis...")
    analyzer = SentimentAnalyzer()

    platforms = ["Twitter", "Reddit", "Discord"]
    queries = ["#Bitcoin", "#ETH", "#Solana"]

    for platform in platforms:
        for query in queries:
            print(f"\nAnalyzing {platform} for {query}")
            try:
                results = await analyzer.analyze_social_media(platform, query, limit=3)
                print(json.dumps(results, ensure_ascii=False, indent=2))
            except Exception as e:
                print(f"Error analyzing social media: {str(e)}")


async def test_news_analysis():
    """Test news sentiment analysis."""
    print("\nTesting news analysis...")
    analyzer = SentimentAnalyzer()

    symbols = ["BTC", "ETH", "SOL"]
    days = [1, 7]

    for symbol in symbols:
        for day in days:
            print(f"\nAnalyzing news for {symbol} over {day} days")
            try:
                results = await analyzer.analyze_news(symbol, day)
                print(json.dumps(results, ensure_ascii=False, indent=2))
            except Exception as e:
                print(f"Error analyzing news: {str(e)}")


async def test_market_sentiment():
    """Test market sentiment analysis."""
    print("\nTesting market sentiment...")
    analyzer = SentimentAnalyzer()

    symbols = ["BTC", "ETH", "SOL"]

    for symbol in symbols:
        print(f"\nAnalyzing market sentiment for {symbol}")
        try:
            result = await analyzer.get_market_sentiment(symbol)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"Error analyzing market sentiment: {str(e)}")


async def main():
    """Run all tests."""
    print("Starting sentiment analyzer tests...")

    try:
        await test_text_analysis()
        await test_social_media_analysis()
        await test_news_analysis()
        await test_market_sentiment()

        print("\nAll tests completed successfully!")

    except Exception as e:
        print(f"\nTest suite failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

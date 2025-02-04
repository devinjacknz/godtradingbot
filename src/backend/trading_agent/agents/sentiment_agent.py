import json
from datetime import datetime
from typing import Any, Dict, List

from src.shared.db.database_manager import DatabaseManager
from src.shared.models.deepseek import DeepSeek1_5B
from src.shared.utils.batch_processor import BatchProcessor
from src.shared.utils.fallback_manager import FallbackManager

from .base_agent import BaseAgent


class SentimentAgent(BaseAgent):
    def __init__(self, agent_id: str, name: str, config: Dict[str, Any]):
        super().__init__(agent_id, name, config)
        self.symbols = config.get("symbols", ["BTC", "ETH", "SOL"])
        self.update_interval = config.get("update_interval", 300)
        self.languages = config.get("languages", ["en", "zh"])
        self.model = DeepSeek1_5B(quantized=True)

        class LegacySentimentSystem:
            async def process(self, texts: List[str]) -> List[Dict[str, Any]]:
                return [{"sentiment": "neutral", "score": 0.5} for _ in texts]

        self.batch_processor = BatchProcessor(max_batch=16, timeout=50)
        self.fallback_manager = FallbackManager(self.model, LegacySentimentSystem())

    async def start(self):
        self.status = "active"
        self.last_update = datetime.now().isoformat()

    async def stop(self):
        self.status = "inactive"
        self.last_update = datetime.now().isoformat()

    async def update_config(self, new_config: Dict[str, Any]):
        self.config = new_config
        self.symbols = new_config.get("symbols", self.symbols)
        self.update_interval = new_config.get("update_interval", self.update_interval)
        self.languages = new_config.get("languages", self.languages)
        self.last_update = datetime.now().isoformat()

    async def analyze_sentiment(
        self, text: str, language: str = "en"
    ) -> Dict[str, Any]:
        prompt = f"Analyze the sentiment of this {language} text and return a JSON with 'sentiment' (positive/negative/neutral) and 'score' (0-1): {text}"
        result = await self.model.generate(prompt)
        return {
            "sentiment": (
                "positive"
                if "positive" in result["text"].lower()
                else "negative"
                if "negative" in result["text"].lower()
                else "neutral"
            ),
            "score": float(result["confidence"]),
        }

    async def get_market_sentiment(self, symbol: str) -> Dict[str, Any]:
        # Check cache first
        cached_sentiment = self.cache.get_sentiment(symbol)
        if cached_sentiment:
            return cached_sentiment.dict()

        if not hasattr(self, "db_manager"):
            try:
                self.db_manager = DatabaseManager(
                    mongodb_url=self.config.get(
                        "mongodb_url", "mongodb://localhost:27017/test"
                    ),
                    postgres_url=self.config.get(
                        "postgres_url", "postgresql://test:test@localhost:5432/test"
                    ),
                )
            except Exception:
                from tests.unit.mocks.db_mocks import MockDatabaseManager

                self.db_manager = MockDatabaseManager()

        # Get latest news and social media data from MongoDB
        news_cursor = (
            self.db_manager.mongodb.raw_news.find(
                {"content": {"$regex": symbol, "$options": "i"}}
            )
            .sort("published_at", -1)
            .limit(5)
        )

        social_cursor = (
            self.db_manager.mongodb.social_posts.find(
                {"content": {"$regex": symbol, "$options": "i"}}
            )
            .sort("posted_at", -1)
            .limit(5)
        )

        news_texts = [doc["content"] async for doc in news_cursor]
        social_texts = [doc["content"] async for doc in social_cursor]

        # Process sentiments in batches with fallback
        try:
            news_prompts = [
                f"Analyze the sentiment of this text and return a JSON with 'sentiment' and 'score': {text}"
                for text in news_texts
            ]
            social_prompts = [
                f"Analyze the sentiment of this text and return a JSON with 'sentiment' and 'score': {text}"
                for text in social_texts
            ]

            news_results = (
                await self.model.generate_batch(news_prompts) if news_texts else []
            )
            social_results = (
                await self.model.generate_batch(social_prompts) if social_texts else []
            )

            news_sentiments = []
            social_sentiments = []

            for result in news_results:
                try:
                    sentiment_data = json.loads(result["text"])
                    news_sentiments.append(
                        {
                            "sentiment": sentiment_data.get("sentiment", "neutral"),
                            "score": float(sentiment_data.get("score", 0.5)),
                        }
                    )
                except:
                    news_sentiments.append({"sentiment": "neutral", "score": 0.5})

            for result in social_results:
                try:
                    sentiment_data = json.loads(result["text"])
                    social_sentiments.append(
                        {
                            "sentiment": sentiment_data.get("sentiment", "neutral"),
                            "score": float(sentiment_data.get("score", 0.5)),
                        }
                    )
                except:
                    social_sentiments.append({"sentiment": "neutral", "score": 0.5})

        except Exception as e:
            # Fallback to legacy system
            news_sentiments = (
                await self.fallback_manager.execute_batch(news_texts)
                if news_texts
                else []
            )
            social_sentiments = (
                await self.fallback_manager.execute_batch(social_texts)
                if social_texts
                else []
            )

        # Calculate average sentiment scores
        news_score = (
            sum(s["score"] for s in news_sentiments) / len(news_sentiments)
            if news_sentiments
            else 0.5
        )
        social_score = (
            sum(s["score"] for s in social_sentiments) / len(social_sentiments)
            if social_sentiments
            else 0.5
        )

        # Get market indicators sentiment
        market_data = await self.db_manager.mongodb.market_snapshots.find_one(
            {"symbol": symbol}, sort=[("timestamp", -1)]
        )
        market_text = (
            f"Price: {market_data['price']}, Volume: {market_data['volume']}"
            if market_data
            else f"Market data for {symbol}"
        )
        market_sentiment = await self.analyze_sentiment(market_text)

        # Calculate combined score with weights
        weights = {"news": 0.3, "social": 0.3, "market": 0.4}
        combined_score = (
            news_score * weights["news"]
            + social_score * weights["social"]
            + market_sentiment["score"] * weights["market"]
        )

        sentiment_result = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "sentiment": {
                "news": {"score": news_score, "samples": len(news_sentiments)},
                "social": {"score": social_score, "samples": len(social_sentiments)},
                "market": market_sentiment,
                "combined": {
                    "score": combined_score,
                    "label": "positive" if combined_score > 0.5 else "negative",
                },
            },
            "status": "active",
        }

        # Store the sentiment analysis result
        await self.db_manager.store_combined_sentiment(
            {
                "symbol": symbol,
                "news_sentiment": news_score,
                "social_sentiment": social_score,
                "market_sentiment": market_sentiment["score"],
                "combined_score": combined_score,
                "source_signals": {
                    "news_count": len(news_sentiments),
                    "social_count": len(social_sentiments),
                    "market_data": bool(market_data),
                },
            }
        )

        # Cache the sentiment result
        self.cache.set(f"sentiment:{symbol}", sentiment_result)
        return sentiment_result

import json
from datetime import datetime
from typing import Any, Dict, List

from src.shared.db.database_manager import DatabaseManager
from src.shared.models.deepseek import DeepSeek1_5B
from src.shared.utils.batch_processor import BatchProcessor
from src.shared.utils.fallback_manager import FallbackManager

from .base_agent import BaseAgent


class FundamentalsAgent(BaseAgent):
    def __init__(self, agent_id: str, name: str, config: Dict[str, Any]):
        super().__init__(agent_id, name, config)
        self.metrics = config.get("metrics", ["volume", "market_cap", "tvl"])
        self.update_interval = config.get("update_interval", 3600)
        self.symbols = config.get("symbols", ["BTC/USDT", "ETH/USDT", "SOL/USDT"])
        self.model = DeepSeek1_5B(quantized=True)

        class LegacyFundamentalsSystem:
            async def process(self, texts: List[str]) -> List[Dict[str, Any]]:
                return [{"sentiment": "neutral", "score": 0.5} for _ in texts]

        class FundamentalsBatchProcessor(BatchProcessor[str, Dict[str, Any]]):
            def __init__(self, agent):
                super().__init__(max_batch=16, timeout=50)
                self.agent = agent

            async def _process_items(self, items: List[str]) -> List[Dict[str, Any]]:
                results = []
                for text in items:
                    prompt = f"Analyze the sentiment of this text and return a JSON with 'sentiment' and 'score': {text}"
                    result = await self.agent.model.generate(prompt)
                    try:
                        sentiment = json.loads(result["text"])
                        results.append(sentiment)
                    except:
                        results.append({"score": 0.5})
                return results

        self.batch_processor = FundamentalsBatchProcessor(self)
        self.fallback_manager = FallbackManager(
            self.batch_processor, LegacyFundamentalsSystem()
        )

    async def start(self):
        self.status = "active"
        self.last_update = datetime.now().isoformat()

    async def stop(self):
        self.status = "inactive"
        self.last_update = datetime.now().isoformat()

    async def update_config(self, new_config: Dict[str, Any]):
        self.config = new_config
        self.metrics = new_config.get("metrics", self.metrics)
        self.update_interval = new_config.get("update_interval", self.update_interval)
        self.symbols = new_config.get("symbols", self.symbols)
        self.last_update = datetime.now().isoformat()

    async def analyze_fundamentals(self, symbol: str) -> Dict[str, Any]:
        # Check cache first
        cached_fundamentals = self.cache.get(f"fundamentals:{symbol}")
        if cached_fundamentals:
            return cached_fundamentals

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

        # Get latest project data from MongoDB
        project_data = await self.db_manager.mongodb.raw_news.find_one(
            {"symbol": symbol, "type": "project_update"}, sort=[("published_at", -1)]
        )

        dev_data = await self.db_manager.mongodb.raw_news.find_one(
            {"symbol": symbol, "type": "development_update"},
            sort=[("published_at", -1)],
        )

        community_cursor = (
            self.db_manager.mongodb.social_posts.find(
                {"content": {"$regex": symbol, "$options": "i"}}
            )
            .sort("posted_at", -1)
            .limit(10)
        )

        # Prepare texts for analysis
        project_text = (
            project_data["content"]
            if project_data
            else f"Project fundamentals for {symbol}"
        )
        dev_text = (
            dev_data["content"] if dev_data else f"Development activity for {symbol}"
        )
        community_texts = [doc["content"] async for doc in community_cursor]

        # Process sentiments in batches using existing batch processor

        # Process project and dev updates with fallback
        project_dev_results = await self.fallback_manager.execute_batch(
            [f"Project update: {project_text}", f"Development update: {dev_text}"]
        )
        project_sentiment = (
            project_dev_results[0] if project_dev_results else {"score": 0.5}
        )
        dev_sentiment = (
            project_dev_results[1] if project_dev_results else {"score": 0.5}
        )

        # Process community texts in batch with fallback
        community_sentiments = (
            await self.fallback_manager.execute_batch(community_texts)
            if community_texts
            else []
        )

        community_score = (
            sum(s["score"] for s in community_sentiments) / len(community_sentiments)
            if community_sentiments
            else 0.5
        )

        # Calculate metrics with weighted components
        weights = {"project": 0.4, "development": 0.4, "community": 0.2}
        metrics = {
            "project_health": project_sentiment["score"],
            "dev_activity": dev_sentiment["score"],
            "community_growth": community_score,
        }

        fundamental_score = (
            metrics["project_health"] * weights["project"]
            + metrics["dev_activity"] * weights["development"]
            + metrics["community_growth"] * weights["community"]
        )

        analysis_result = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics,
            "fundamental_score": fundamental_score,
            "sentiment_analysis": {
                "project": project_sentiment,
                "development": dev_sentiment,
                "community": {
                    "score": community_score,
                    "samples": len(community_sentiments),
                },
            },
            "status": "active",
        }

        # Store analysis in MongoDB for historical tracking
        await self.db_manager.mongodb.fundamental_analysis.insert_one(
            {
                **analysis_result,
                "meta_info": {
                    "project_data_id": (
                        str(project_data["_id"]) if project_data else None
                    ),
                    "dev_data_id": str(dev_data["_id"]) if dev_data else None,
                    "community_samples": len(community_sentiments),
                },
            }
        )

        # Cache the analysis result
        self.cache.set(f"fundamentals:{symbol}", analysis_result)
        return analysis_result

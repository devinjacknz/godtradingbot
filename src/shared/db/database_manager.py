from datetime import datetime
from typing import Any, Dict, List, Optional

import motor.motor_asyncio
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

from ..models.mongodb import (
    AgentAnalysisResult,
    MarketDataSnapshot,
    RawNewsArticle,
    RawSocialMediaPost,
    UnstructuredAnalysis,
)
from ..models.sentiment import (
    AgentSentimentSignal,
    CombinedMarketSentiment,
    SentimentAnalysis,
)
from ..models.strategy import Strategy
from ..models.wallet import Wallet
from .exceptions import ConnectionError, MongoDBError, PostgreSQLError, ValidationError


class DatabaseManager:
    def __init__(self, mongodb_url: str, postgres_url: str):
        try:
            # MongoDB setup
            self.mongodb_client = motor.motor_asyncio.AsyncIOMotorClient(mongodb_url)
            db_name = mongodb_url.split("/")[-1].split("?")[0]
            self.mongodb = self.mongodb_client[db_name]

            # PostgreSQL setup
            self.postgres_engine = create_async_engine(postgres_url)
            self.async_session = sessionmaker(
                self.postgres_engine, class_=AsyncSession, expire_on_commit=False
            )
        except Exception as e:
            if hasattr(self, "mongodb_client"):
                self.mongodb_client.close()
            raise ConnectionError("Failed to initialize database connections", e)

    async def store_raw_news(self, news: RawNewsArticle) -> str:
        try:
            result = await self.mongodb.raw_news.insert_one(news.model_dump())
            return str(result.inserted_id)
        except Exception as e:
            raise MongoDBError("Failed to store raw news", e)

    async def store_social_post(self, post: RawSocialMediaPost) -> str:
        try:
            result = await self.mongodb.social_posts.insert_one(post.model_dump())
            return str(result.inserted_id)
        except Exception as e:
            raise MongoDBError("Failed to store social media post", e)

    async def store_market_snapshot(self, snapshot: MarketDataSnapshot) -> str:
        try:
            result = await self.mongodb.market_snapshots.insert_one(snapshot.dict())
            return str(result.inserted_id)
        except Exception as e:
            raise MongoDBError("Failed to store market snapshot", e)

    async def store_unstructured_analysis(self, analysis: UnstructuredAnalysis) -> str:
        try:
            result = await self.mongodb.unstructured_analysis.insert_one(
                analysis.dict()
            )
            return str(result.inserted_id)
        except Exception as e:
            raise MongoDBError("Failed to store unstructured analysis", e)

    async def store_agent_analysis(self, analysis: AgentAnalysisResult) -> str:
        try:
            result = await self.mongodb.agent_analysis.insert_one(analysis.dict())
            return str(result.inserted_id)
        except Exception as e:
            raise MongoDBError("Failed to store agent analysis", e)

    def _validate_float(self, value: Any, field: str) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValidationError(
                f"Invalid value for {field}: {value} (must be a number)"
            )

    async def store_sentiment_analysis(
        self, sentiment: Dict[str, Any]
    ) -> SentimentAnalysis:
        try:
            # Validate numeric fields
            if "score" in sentiment:
                sentiment["score"] = self._validate_float(sentiment["score"], "score")

            async with self.async_session() as session:
                analysis = SentimentAnalysis(**sentiment)
                session.add(analysis)
                await session.commit()
                return analysis
        except SQLAlchemyError as e:
            raise PostgreSQLError("Failed to store sentiment analysis", e)
        except ValidationError as e:
            raise e
        except Exception as e:
            raise ValidationError("Invalid sentiment data", e)

    async def store_agent_sentiment(
        self, sentiment: Dict[str, Any]
    ) -> AgentSentimentSignal:
        try:
            # Validate numeric fields
            sentiment["sentiment_score"] = self._validate_float(
                sentiment["sentiment_score"], "sentiment_score"
            )
            sentiment["confidence"] = self._validate_float(
                sentiment["confidence"], "confidence"
            )
            sentiment["signal_strength"] = self._validate_float(
                sentiment["signal_strength"], "signal_strength"
            )

            async with self.async_session() as session:
                signal = AgentSentimentSignal(**sentiment)
                session.add(signal)
                await session.commit()
                return signal
        except SQLAlchemyError as e:
            raise PostgreSQLError("Failed to store agent sentiment", e)
        except ValidationError as e:
            raise e
        except Exception as e:
            raise ValidationError("Invalid agent sentiment data", e)

    async def store_combined_sentiment(
        self, sentiment: Dict[str, Any]
    ) -> CombinedMarketSentiment:
        try:
            # Validate numeric fields
            sentiment["news_sentiment"] = self._validate_float(
                sentiment["news_sentiment"], "news_sentiment"
            )
            sentiment["social_sentiment"] = self._validate_float(
                sentiment["social_sentiment"], "social_sentiment"
            )
            sentiment["market_sentiment"] = self._validate_float(
                sentiment["market_sentiment"], "market_sentiment"
            )
            sentiment["combined_score"] = self._validate_float(
                sentiment["combined_score"], "combined_score"
            )

            async with self.async_session() as session:
                combined = CombinedMarketSentiment(**sentiment)
                session.add(combined)
                await session.commit()
                return combined
        except SQLAlchemyError as e:
            raise PostgreSQLError("Failed to store combined sentiment", e)
        except ValidationError as e:
            raise e
        except Exception as e:
            raise ValidationError("Invalid combined sentiment data", e)

    async def get_latest_market_sentiment(
        self, symbol: str
    ) -> Optional[CombinedMarketSentiment]:
        try:
            async with self.async_session() as session:
                query = (
                    select(CombinedMarketSentiment)
                    .filter_by(symbol=symbol)
                    .order_by(CombinedMarketSentiment.created_at.desc())
                )
                result = await session.execute(query)
                return result.scalars().first()
        except SQLAlchemyError as e:
            raise PostgreSQLError("Failed to fetch market sentiment", e)

    async def get_raw_news_by_source(
        self, source: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        try:
            cursor = self.mongodb.raw_news.find({"source": source}).limit(limit)
            return [doc async for doc in cursor]
        except Exception as e:
            raise MongoDBError("Failed to fetch raw news", e)

    async def get_social_posts_by_platform(
        self, platform: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        try:
            cursor = self.mongodb.social_posts.find({"platform": platform}).limit(limit)
            return [doc async for doc in cursor]
        except Exception as e:
            raise MongoDBError("Failed to fetch social posts", e)

    async def close(self):
        try:
            if hasattr(self, "mongodb_client"):
                self.mongodb_client.close()
            if hasattr(self, "postgres_engine"):
                await self.postgres_engine.dispose()
        except Exception as e:
            raise ConnectionError("Failed to close database connections", e)

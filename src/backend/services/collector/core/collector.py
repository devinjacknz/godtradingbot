import asyncio
import inspect
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union

import aiohttp
from bs4 import BeautifulSoup
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tradingbot.shared.models.mongodb import RawNewsArticle
from tradingbot.shared.models.sentiment import SentimentAnalysis
from tradingbot.shared.sentiment.sentiment_analyzer import analyze_text


class NewsCollector:
    """Collects news from various crypto news sources."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.sources = {
            "coindesk": "https://www.coindesk.com",
            "cointelegraph": "https://cointelegraph.com",
            "decrypt": "https://decrypt.co",
        }
        self.chinese_sources = {
            "binance_cn": "https://www.binance.com/zh-CN/news",
            "odaily": "https://www.odaily.news",
            "jinse": "https://www.jinse.com",
        }
        self.session = None

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def initialize(self):
        """Initialize the collector."""
        self.session = aiohttp.ClientSession()

    async def close(self):
        """Clean up resources."""
        if hasattr(self, "session"):
            await self.session.close()

    async def collect_news(self, timeframe_hours: int = 24) -> List[Dict[str, Any]]:
        """Collect news from all configured sources."""
        cutoff_time = datetime.now() - timedelta(hours=timeframe_hours)
        all_news = []

        for source, url in {**self.sources, **self.chinese_sources}.items():
            try:
                news = await self._fetch_news(source, url, cutoff_time)
                all_news.extend(news)
            except Exception as e:
                print(f"Error collecting news from {source}: {str(e)}")

        return sorted(all_news, key=lambda x: x["timestamp"], reverse=True)

    async def _fetch_news(
        self, source: str, url: str, cutoff_time: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch news from a specific source."""
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return []

                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                articles = []
                for article in soup.find_all("article")[
                    :10
                ]:  # Limit to recent articles
                    title = article.find("h2")
                    if not title:
                        continue

                    link = article.find("a")
                    timestamp = article.find("time")

                    articles.append(
                        {
                            "title": title.text.strip(),
                            "url": link["href"] if link else None,
                            "source": source,
                            "timestamp": datetime.now(),  # Placeholder, should parse actual timestamp
                            "content": "",  # Would need to fetch full article
                            "language": (
                                "zh" if source in self.chinese_sources else "en"
                            ),
                        }
                    )

                return articles
        except Exception as e:
            print(f"Error fetching from {source}: {str(e)}")
            return []

    async def process_source(self, url: str, name: str, parser: callable) -> None:
        """Process a news source and analyze sentiment."""
        try:
            # Handle both async and sync parsers
            if asyncio.iscoroutinefunction(parser):
                articles = await parser(url)
            else:
                articles = parser(url)

            if not isinstance(articles, list):
                raise ValueError("Parser must return a list of articles")

            for article in articles:
                try:
                    if isinstance(article, dict):
                        # Create RawNewsArticle instance from dict
                        raw_article = RawNewsArticle(
                            source=name,
                            title=article["title"],
                            url=article["url"],
                            content=article.get("content", ""),
                            author=article.get("author"),
                            published_at=article.get("timestamp", datetime.now()),
                            analysis_metadata={
                                "language": article.get("language", "en")
                            },
                        )
                    else:
                        # Use article directly if it's already a RawNewsArticle
                        raw_article = article

                    # Analyze sentiment
                    sentiment = await analyze_text(
                        raw_article.content,
                        language=raw_article.analysis_metadata["language"],
                    )

                    # Use mocked sentiment for testing
                    sentiment_result = await analyze_text(
                        raw_article.content,
                        language=raw_article.analysis_metadata.get("language", "en"),
                    )

                    # Store sentiment in article metadata
                    raw_article.metadata["sentiment"] = sentiment_result.copy()

                    # Create sentiment analysis record
                    analysis = SentimentAnalysis(
                        source_id=raw_article.url,
                        score=sentiment_result["score"],
                        sentiment=sentiment_result["sentiment"],
                        language=sentiment_result["language"],
                        raw_text=raw_article.content,
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                    )

                    # Save to database
                    engine = create_engine(
                        os.getenv(
                            "DATABASE_URL",
                            "postgresql://postgres:postgres@localhost:5432/test_db",
                        )
                    )
                    with Session(engine) as session:
                        session.add(analysis)
                        session.commit()
                    print(f"Saving sentiment analysis for {raw_article.url}")
                except Exception as e:
                    print(
                        f"Error processing article {getattr(article, 'url', 'unknown')}: {str(e)}"
                    )
                    continue
        except Exception as e:
            print(f"Error processing source {name}: {str(e)}")

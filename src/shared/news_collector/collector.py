import asyncio
import inspect
import os
import random
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

import aiohttp
from bs4 import BeautifulSoup
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.shared.models.mongodb import RawNewsArticle
from src.shared.models.sentiment import SentimentAnalysis
from src.shared.sentiment.sentiment_analyzer import analyze_text


class NewsCollector:
    """Collects news from various crypto news sources."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.sources = {
            "coindesk": "https://www.coindesk.com",
            "cointelegraph": "https://cointelegraph.com",
            "decrypt": "https://decrypt.co",
            "bloomberg": "https://www.bloomberg.com/crypto",
            "reuters": "https://www.reuters.com/markets/currencies/crypto",
            "cryptoslate": "https://cryptoslate.com",
            "ambcrypto": "https://ambcrypto.com",
        }
        self.chinese_sources = {
            "binance_cn": "https://www.binance.com/zh-CN/news",
            "odaily": "https://www.odaily.news",
            "jinse": "https://www.jinse.com",
            "theblockbeats": "https://www.theblockbeats.info",
            "chaincatcher": "https://www.chaincatcher.com",
            "foresightnews": "https://foresightnews.pro/news",
        }
        self.social_sources = {"bwenews": "https://t.me/s/BWEnews"}
        self.session = None

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def _get_random_user_agent(self):
        """Get a random user agent string."""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        ]
        return random.choice(user_agents)

    async def initialize(self):
        """Initialize the collector."""
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "User-Agent": self._get_random_user_agent(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5,zh-CN;q=0.3",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            },
        )

    async def close(self):
        """Clean up resources."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def collect_news(self, timeframe_hours: int = 24) -> List[Dict[str, Any]]:
        """Collect news from all configured sources."""
        cutoff_time = datetime.now() - timedelta(hours=timeframe_hours)
        all_news = []

        all_sources = {**self.sources, **self.chinese_sources, **self.social_sources}

        for source, url in all_sources.items():
            try:
                if source == "bwenews":
                    news = await self._fetch_telegram_news(url, cutoff_time)
                else:
                    news = await self._fetch_news(source, url, cutoff_time)
                all_news.extend(news)
            except Exception as e:
                print(f"Error collecting news from {source}: {str(e)}")

        return sorted(all_news, key=lambda x: x["timestamp"], reverse=True)

    async def _fetch_news(
        self, source: str, url: str, cutoff_time: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch news from a specific source."""
        if not self.session:
            print(f"Error: Session not initialized for {source}")
            return []

        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                self.session._default_headers[
                    "User-Agent"
                ] = self._get_random_user_agent()

                async with self.session.get(
                    url, allow_redirects=True, ssl=False, timeout=30
                ) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, "html.parser")

                        articles = []
                        selectors = {
                            "bloomberg": {
                                "article": "article.story-package-module__story",
                                "title": "h3.story-package-module__headline",
                                "link": "a.story-package-module__headline__link",
                                "time": "time.story-package-module__timestamp",
                            },
                            "reuters": {
                                "article": "article.media-story-card",
                                "title": "h3.media-story-card__heading__eqhp9",
                                "link": "a.media-story-card__heading__eqhp9",
                                "time": "time.media-story-card__datetime__eqhp9",
                            },
                            "cryptoslate": {
                                "article": "article.post-card",
                                "title": "h2.post-title",
                                "link": "a.post-title-link",
                                "time": "time.post-date",
                            },
                            "ambcrypto": {
                                "article": "article.jeg_post",
                                "title": "h3.jeg_post_title",
                                "link": "a.jeg_post_title",
                                "time": "div.jeg_meta_date",
                            },
                            "theblockbeats": {
                                "article": "div.news-item",
                                "title": "h3.news-title",
                                "link": "a.news-link",
                                "time": "span.time",
                            },
                            "chaincatcher": {
                                "article": "div.article-item",
                                "title": "h3.article-title",
                                "link": "a.article-link",
                                "time": "span.time",
                            },
                            "foresightnews": {
                                "article": "div.news-item",
                                "title": "h3.news-title",
                                "link": "a.news-link",
                                "time": "span.time",
                            },
                            "binance_cn": {
                                "article": "div.css-1wr4jig",
                                "title": "h3.css-1nqr3i7",
                                "link": "a.css-1nqr3i7",
                                "time": "span.css-1gqo2zd",
                            },
                            "odaily": {
                                "article": "div.article-item",
                                "title": "h3.article-title",
                                "link": "a.article-link",
                                "time": "span.time",
                            },
                            "jinse": {
                                "article": "div.content-item",
                                "title": "h3.content-title",
                                "link": "a.content-link",
                                "time": "span.time",
                            },
                            "coindesk": {
                                "article": "div.article-cardstyles__StyledWrapper-sc-q1x8lc-0",
                                "title": "h6.typography__StyledTypography-sc-owin6q-0",
                                "link": "a.card-title",
                                "time": "span.date-modified",
                            },
                            "cointelegraph": {
                                "article": "article.post-card-inline",
                                "title": "span.post-card-inline__title",
                                "link": "a.post-card-inline__title-link",
                                "time": "time.post-card-inline__date",
                            },
                            "decrypt": {
                                "article": "article.storyCard",
                                "title": "h3.heading",
                                "link": "a.storyCard__link",
                                "time": "time.timestamp",
                            },
                        }.get(
                            source,
                            {
                                "article": "article",
                                "title": "h2,h3",
                                "link": "a",
                                "time": "time",
                            },
                        )

                        for article in soup.select(selectors["article"])[:10]:
                            title_elem = article.select_one(selectors["title"])
                            link_elem = article.select_one(selectors["link"])
                            time_elem = article.select_one(selectors["time"])

                            if not title_elem:
                                continue

                            title = title_elem.get_text(strip=True)
                            href = link_elem.get("href") if link_elem else None

                            if href and isinstance(href, str) and href.startswith("/"):
                                href = f"{url.rstrip('/')}{href}"

                            timestamp = (
                                self._parse_timestamp(time_elem.get_text(strip=True))
                                if time_elem
                                else datetime.now()
                            )

                            if timestamp >= cutoff_time:
                                articles.append(
                                    {
                                        "title": title,
                                        "url": href,
                                        "source": source,
                                        "timestamp": timestamp,
                                        "content": "",
                                        "language": (
                                            "zh"
                                            if source in self.chinese_sources
                                            else "en"
                                        ),
                                    }
                                )

                        return articles

                    elif response.status in [403, 401]:
                        print(
                            f"Access denied for {source}, attempt {attempt + 1}/{max_retries}"
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue
                    else:
                        print(f"Error fetching {source}: HTTP {response.status}")
                        return []

            except Exception as e:
                print(f"Error fetching {source}: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                return []
        return []

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse timestamp string to datetime object."""
        try:
            # Common patterns
            patterns = [
                # ISO format
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S",
                # Common news site formats
                "%B %d, %Y %H:%M",
                "%b %d, %Y %H:%M",
                "%Y-%m-%d %H:%M",
                "%d %b %Y",
                "%Y年%m月%d日 %H:%M",  # Chinese format
                "%m月%d日 %H:%M",  # Short Chinese format
                # Relative time conversion (approximate)
                "刚刚",
                "just now",
                "分钟前",
                "minutes ago",
                "小时前",
                "hours ago",
                "天前",
                "days ago",
            ]

            timestamp_str = timestamp_str.strip().lower()
            now = datetime.now()

            # Handle relative times
            if any(x in timestamp_str for x in ["ago", "前"]):
                if any(x in timestamp_str for x in ["minute", "分钟"]):
                    minutes = int("".join(filter(str.isdigit, timestamp_str)))
                    return now - timedelta(minutes=minutes)
                elif any(x in timestamp_str for x in ["hour", "小时"]):
                    hours = int("".join(filter(str.isdigit, timestamp_str)))
                    return now - timedelta(hours=hours)
                elif any(x in timestamp_str for x in ["day", "天"]):
                    days = int("".join(filter(str.isdigit, timestamp_str)))
                    return now - timedelta(days=days)

            # Handle "just now" cases
            if timestamp_str in ["刚刚", "just now"]:
                return now

            # Try parsing with different formats
            for pattern in patterns:
                try:
                    return datetime.strptime(timestamp_str, pattern)
                except ValueError:
                    continue

            # If all else fails, try ISO format
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except Exception as e:
            print(f"Error parsing timestamp '{timestamp_str}': {str(e)}")
            return datetime.now()

    async def _fetch_telegram_news(
        self, url: str, cutoff_time: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch news from Telegram channel."""
        if not self.session:
            print("Error: Session not initialized for Telegram")
            return []

        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return []

                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                articles = []
                for message in soup.select(".tgme_widget_message_text")[:10]:
                    articles.append(
                        {
                            "title": (
                                message.text[:100] + "..."
                                if len(message.text) > 100
                                else message.text
                            ),
                            "url": url,
                            "source": "bwenews",
                            "timestamp": datetime.now(),
                            "content": message.text,
                            "language": "en",
                        }
                    )

                return articles
        except Exception as e:
            print(f"Error fetching from Telegram: {str(e)}")
            return []

    async def process_source(
        self,
        url: str,
        name: str,
        parser: Callable[
            [str], Union[List[Dict[str, Any]], Awaitable[List[Dict[str, Any]]]]
        ],
    ) -> None:
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
                        raw_article = article

                    sentiment_result = await analyze_text(
                        raw_article.content,
                        language=raw_article.analysis_metadata.get("language", "en"),
                    )

                    raw_article.metadata["sentiment"] = sentiment_result.copy()

                    analysis = SentimentAnalysis(
                        source_id=raw_article.url,
                        score=sentiment_result["score"],
                        sentiment=sentiment_result["sentiment"],
                        metadata={
                            "language": raw_article.analysis_metadata.get(
                                "language", "en"
                            )
                        },
                    )

                    raw_article.save()
                    analysis.save()
                except Exception as e:
                    print(f"Error processing article from {name}: {str(e)}")
                    continue
        except Exception as e:
            print(f"Error processing source {name}: {str(e)}")
        return None

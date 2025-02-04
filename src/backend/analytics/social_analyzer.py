import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from prometheus_client import Counter, Gauge, Histogram
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer
from textblob import TextBlob


class SentimentLevel(Enum):
    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"


@dataclass
class SocialMetrics:
    """社交媒体指标"""

    sentiment_score: Gauge
    mention_count: Counter
    trend_strength: Gauge
    influence_score: Gauge
    analysis_count: Counter
    processing_time: Histogram


class SocialAnalyzer:
    def __init__(self, config: Dict):
        self.config = config
        self.sentiment_history = []
        self.topic_clusters = {}
        self.influencer_stats = {}

        # 社交媒体指标
        self.metrics = SocialMetrics(
            sentiment_score=Gauge("social_sentiment_score", "Overall sentiment score"),
            mention_count=Counter("social_mention_count", "Number of mentions"),
            trend_strength=Gauge("social_trend_strength", "Current trend strength"),
            influence_score=Gauge("social_influence_score", "Influencer impact score"),
            analysis_count=Counter(
                "social_analysis_count", "Number of analyses performed"
            ),
            processing_time=Histogram(
                "social_processing_time", "Analysis processing time"
            ),
        )

        # 分析配置
        self.analysis_config = {
            "sentiment_threshold": config.get("sentiment_threshold", 0.3),
            "trend_detection_window": config.get("trend_detection_window", 1000),
            "influence_threshold": config.get("influence_threshold", 0.7),
            "update_interval": config.get("update_interval", 60),
            "min_cluster_size": config.get("min_cluster_size", 5),
        }

        # 初始化分析任务
        self.analyzer_task = None

        # 初始化文本向量化器
        self.vectorizer = TfidfVectorizer(
            max_features=1000, stop_words="english", ngram_range=(1, 2)
        )

    async def start(self):
        """启动社交媒体分析系统"""
        self.analyzer_task = asyncio.create_task(self._analyze_social_data())

    async def stop(self):
        """停止社交媒体分析系统"""
        if self.analyzer_task:
            self.analyzer_task.cancel()
            try:
                await self.analyzer_task
            except asyncio.CancelledError:
                pass

    async def _analyze_social_data(self):
        """社交媒体数据分析循环"""
        while True:
            try:
                start_time = time.time()

                # 获取新数据
                new_data = await self._fetch_social_data()

                # 情感分析
                await self._analyze_sentiment(new_data)

                # 趋势检测
                await self._detect_trends(new_data)

                # 影响力分析
                await self._analyze_influence(new_data)

                # 记录处理时间
                processing_time = time.time() - start_time
                self.metrics.processing_time.observe(processing_time)

                # 更新分析计数
                self.metrics.analysis_count.inc()

                # 等待下一次分析
                await asyncio.sleep(self.analysis_config["update_interval"])

            except Exception as e:
                self.logger.error(f"Error in social data analysis: {str(e)}")
                await asyncio.sleep(1)

    async def _analyze_sentiment(self, data: List[Dict]):
        """情感分析"""
        try:
            sentiments = []
            for item in data:
                # 使用TextBlob进行情感分析
                blob = TextBlob(item["text"])
                sentiment = blob.sentiment.polarity

                # 记录情感分数
                sentiments.append(
                    {
                        "timestamp": item["timestamp"],
                        "sentiment": sentiment,
                        "followers": item["user_followers"],
                        "engagement": item["engagement_score"],
                    }
                )

            if sentiments:
                # 计算加权情感分数
                weighted_sentiment = np.average(
                    [s["sentiment"] for s in sentiments],
                    weights=[s["followers"] * s["engagement"] for s in sentiments],
                )

                # 更新情感指标
                self.metrics.sentiment_score.set(weighted_sentiment)

                # 更新情感历史
                self.sentiment_history.append(
                    {"timestamp": time.time(), "sentiment": weighted_sentiment}
                )

                # 保持历史窗口大小
                if (
                    len(self.sentiment_history)
                    > self.analysis_config["trend_detection_window"]
                ):
                    self.sentiment_history = self.sentiment_history[
                        -self.analysis_config["trend_detection_window"] :
                    ]

        except Exception as e:
            self.logger.error(f"Error in sentiment analysis: {str(e)}")

    async def _detect_trends(self, data: List[Dict]):
        """趋势检测"""
        try:
            if not data:
                return

            # 提取文本内容
            texts = [item["text"] for item in data]

            # 向量化文本
            text_vectors = self.vectorizer.fit_transform(texts)

            # 使用DBSCAN聚类发现主题
            clustering = DBSCAN(
                eps=0.3, min_samples=self.analysis_config["min_cluster_size"]
            ).fit(text_vectors)

            # 分析聚类结果
            clusters = {}
            for i, label in enumerate(clustering.labels_):
                if label != -1:  # 忽略噪声点
                    if label not in clusters:
                        clusters[label] = []
                    clusters[label].append(data[i])

            # 计算趋势强度
            trend_strengths = []
            for cluster in clusters.values():
                # 计算时间跨度
                timestamps = [item["timestamp"] for item in cluster]
                time_span = max(timestamps) - min(timestamps)

                # 计算参与度
                engagement = sum(item["engagement_score"] for item in cluster)

                # 计算影响力
                influence = sum(item["user_followers"] for item in cluster)

                # 综合计算趋势强度
                strength = (
                    (
                        len(cluster) * 0.4  # 数量权重
                        + engagement * 0.3  # 参与度权重
                        + influence * 0.3  # 影响力权重
                    )
                    / time_span
                    if time_span > 0
                    else 0
                )

                trend_strengths.append(strength)

            # 更新趋势强度指标
            if trend_strengths:
                self.metrics.trend_strength.set(max(trend_strengths))

            # 更新主题聚类
            self.topic_clusters = clusters

        except Exception as e:
            self.logger.error(f"Error in trend detection: {str(e)}")

    async def _analyze_influence(self, data: List[Dict]):
        """影响力分析"""
        try:
            for item in data:
                user_id = item["user_id"]

                # 更新用户统计
                if user_id not in self.influencer_stats:
                    self.influencer_stats[user_id] = {
                        "followers": item["user_followers"],
                        "posts": 0,
                        "total_engagement": 0,
                        "sentiment_impact": 0,
                    }

                stats = self.influencer_stats[user_id]
                stats["posts"] += 1
                stats["total_engagement"] += item["engagement_score"]

                # 计算情感影响力
                sentiment = TextBlob(item["text"]).sentiment.polarity
                stats["sentiment_impact"] += abs(sentiment) * item["engagement_score"]

            # 计算总体影响力分数
            influence_scores = []
            for stats in self.influencer_stats.values():
                if stats["posts"] > 0:
                    score = (
                        np.log1p(stats["followers"]) * 0.4
                        + (stats["total_engagement"] / stats["posts"]) * 0.3
                        + (stats["sentiment_impact"] / stats["posts"]) * 0.3
                    )
                    influence_scores.append(score)

            # 更新影响力指标
            if influence_scores:
                self.metrics.influence_score.set(np.mean(influence_scores))

        except Exception as e:
            self.logger.error(f"Error in influence analysis: {str(e)}")

    def get_social_insights(self) -> Dict:
        """获取社交媒体分析洞察"""
        try:
            # 获取情感趋势
            sentiment_trend = pd.DataFrame(self.sentiment_history)
            if not sentiment_trend.empty:
                sentiment_trend.set_index("timestamp", inplace=True)
                sentiment_trend = sentiment_trend.resample("1H").mean()

            # 获取主要趋势主题
            top_trends = []
            for cluster in self.topic_clusters.values():
                if len(cluster) >= self.analysis_config["min_cluster_size"]:
                    trend = {
                        "size": len(cluster),
                        "engagement": sum(item["engagement_score"] for item in cluster),
                        "influence": sum(item["user_followers"] for item in cluster),
                        "sample_texts": [item["text"] for item in cluster[:3]],
                    }
                    top_trends.append(trend)

            # 按影响力排序趋势
            top_trends.sort(
                key=lambda x: x["influence"] * x["engagement"], reverse=True
            )

            # 获取主要影响者
            top_influencers = []
            for user_id, stats in self.influencer_stats.items():
                if stats["posts"] > 0:
                    influencer = {
                        "user_id": user_id,
                        "followers": stats["followers"],
                        "posts": stats["posts"],
                        "avg_engagement": stats["total_engagement"] / stats["posts"],
                        "sentiment_impact": stats["sentiment_impact"] / stats["posts"],
                    }
                    top_influencers.append(influencer)

            # 按综合影响力排序
            top_influencers.sort(
                key=lambda x: (
                    x["followers"] * x["avg_engagement"] * x["sentiment_impact"]
                ),
                reverse=True,
            )

            return {
                "current_sentiment": self.metrics.sentiment_score._value.get(),
                "sentiment_trend": (
                    sentiment_trend.to_dict() if not sentiment_trend.empty else {}
                ),
                "top_trends": top_trends[:5],  # 返回前5个趋势
                "top_influencers": top_influencers[:10],  # 返回前10个影响者
                "analysis_count": self.metrics.analysis_count._value.get(),
                "last_update": time.time(),
            }

        except Exception as e:
            self.logger.error(f"Error getting social insights: {str(e)}")
            return {}

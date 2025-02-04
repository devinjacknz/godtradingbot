from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import seaborn as sns
from plotly.subplots import make_subplots


class DataVisualizer:
    """数据可视化器，负责生成各类图表"""

    def __init__(self, config: Dict):
        self.config = config
        self.theme = config.get("theme", "plotly_dark")
        self.default_height = config.get("default_height", 600)
        self.default_width = config.get("default_width", 1000)

    def plot_market_overview(
        self, df: pd.DataFrame, save_path: Optional[str] = None
    ) -> go.Figure:
        """生成市场概览图

        Args:
            df: 市场数据
            save_path: 保存路径

        Returns:
            go.Figure: Plotly图形对象
        """
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            subplot_titles=("Price", "Volume"),
            row_heights=[0.7, 0.3],
        )

        # 添加K线图
        fig.add_trace(
            go.Candlestick(
                x=df["timestamp"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="OHLC",
            ),
            row=1,
            col=1,
        )

        # 添加技术指标
        for ma in ["MA5", "MA10", "MA20"]:
            if ma in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df["timestamp"], y=df[ma], name=ma, line=dict(width=1)
                    ),
                    row=1,
                    col=1,
                )

        # 添加成交量图
        fig.add_trace(
            go.Bar(x=df["timestamp"], y=df["volume"], name="Volume"), row=2, col=1
        )

        fig.update_layout(
            template=self.theme,
            height=self.default_height,
            width=self.default_width,
            title="Market Overview",
            xaxis_rangeslider_visible=False,
        )

        if save_path:
            fig.write_html(save_path)

        return fig

    def plot_technical_indicators(
        self, df: pd.DataFrame, save_path: Optional[str] = None
    ) -> go.Figure:
        """生成技术指标图

        Args:
            df: 市场数据
            save_path: 保存路径

        Returns:
            go.Figure: Plotly图形对象
        """
        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=("MACD", "RSI", "Bollinger Bands"),
            row_heights=[0.33, 0.33, 0.34],
        )

        # MACD
        if all(col in df.columns for col in ["MACD", "MACD_signal", "MACD_hist"]):
            fig.add_trace(
                go.Scatter(x=df["timestamp"], y=df["MACD"], name="MACD"), row=1, col=1
            )
            fig.add_trace(
                go.Scatter(x=df["timestamp"], y=df["MACD_signal"], name="Signal"),
                row=1,
                col=1,
            )
            fig.add_trace(
                go.Bar(x=df["timestamp"], y=df["MACD_hist"], name="Histogram"),
                row=1,
                col=1,
            )

        # RSI
        if "RSI" in df.columns:
            fig.add_trace(
                go.Scatter(x=df["timestamp"], y=df["RSI"], name="RSI"), row=2, col=1
            )
            # 添加超买超卖线
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

        # 布林带
        if all(col in df.columns for col in ["BB_upper", "BB_middle", "BB_lower"]):
            fig.add_trace(
                go.Scatter(
                    x=df["timestamp"],
                    y=df["BB_upper"],
                    name="Upper Band",
                    line=dict(dash="dash"),
                ),
                row=3,
                col=1,
            )
            fig.add_trace(
                go.Scatter(x=df["timestamp"], y=df["BB_middle"], name="Middle Band"),
                row=3,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=df["timestamp"],
                    y=df["BB_lower"],
                    name="Lower Band",
                    line=dict(dash="dash"),
                ),
                row=3,
                col=1,
            )
            fig.add_trace(
                go.Scatter(x=df["timestamp"], y=df["close"], name="Close Price"),
                row=3,
                col=1,
            )

        fig.update_layout(
            template=self.theme,
            height=self.default_height,
            width=self.default_width,
            title="Technical Indicators",
        )

        if save_path:
            fig.write_html(save_path)

        return fig

    def plot_trading_analysis(
        self, df: pd.DataFrame, save_path: Optional[str] = None
    ) -> go.Figure:
        """生成交易分析图

        Args:
            df: 交易数据
            save_path: 保存路径

        Returns:
            go.Figure: Plotly图形对象
        """
        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Price vs Volume",
                "Buy/Sell Ratio",
                "Trade Interval Distribution",
                "Price Change Distribution",
            ),
        )

        # 价格和成交量的关系
        fig.add_trace(
            go.Scatter(x=df["price"], y=df["amount"], mode="markers", name="Trades"),
            row=1,
            col=1,
        )

        # 买卖比例
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"], y=df["buy_sell_ratio"], name="Buy/Sell Ratio"
            ),
            row=1,
            col=2,
        )
        fig.add_hline(y=1, line_dash="dash", row=1, col=2)

        # 交易间隔分布
        fig.add_trace(
            go.Histogram(x=df["trade_interval"], name="Trade Intervals"), row=2, col=1
        )

        # 价格变化分布
        fig.add_trace(
            go.Histogram(x=df["price_change"], name="Price Changes"), row=2, col=2
        )

        fig.update_layout(
            template=self.theme,
            height=self.default_height,
            width=self.default_width,
            title="Trading Analysis",
        )

        if save_path:
            fig.write_html(save_path)

        return fig

    def plot_sentiment_analysis(
        self, df: pd.DataFrame, save_path: Optional[str] = None
    ) -> go.Figure:
        """生成情绪分析图

        Args:
            df: 社交媒体数据
            save_path: 保存路径

        Returns:
            go.Figure: Plotly图形对象
        """
        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Sentiment Trend",
                "Sentiment Distribution",
                "Influence vs Sentiment",
                "Platform Breakdown",
            ),
        )

        # 情绪趋势
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"], y=df["sentiment_mean"], name="Average Sentiment"
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df["sentiment_mean"] + df["sentiment_std"],
                name="Upper Bound",
                line=dict(dash="dash"),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df["sentiment_mean"] - df["sentiment_std"],
                name="Lower Bound",
                line=dict(dash="dash"),
            ),
            row=1,
            col=1,
        )

        # 情绪分布
        fig.add_trace(
            go.Histogram(x=df["sentiment"], name="Sentiment Distribution"), row=1, col=2
        )

        # 影响力与情绪的关系
        fig.add_trace(
            go.Scatter(
                x=df["influence_score"],
                y=df["sentiment"],
                mode="markers",
                name="Influence vs Sentiment",
            ),
            row=2,
            col=1,
        )

        # 平台分布
        platform_counts = df["platform"].value_counts()
        fig.add_trace(
            go.Pie(
                labels=platform_counts.index,
                values=platform_counts.values,
                name="Platform Distribution",
            ),
            row=2,
            col=2,
        )

        fig.update_layout(
            template=self.theme,
            height=self.default_height,
            width=self.default_width,
            title="Sentiment Analysis",
        )

        if save_path:
            fig.write_html(save_path)

        return fig

    def plot_correlation_matrix(
        self, df: pd.DataFrame, save_path: Optional[str] = None
    ) -> go.Figure:
        """生成相关性矩阵图

        Args:
            df: 数据框
            save_path: 保存路径

        Returns:
            go.Figure: Plotly图形对象
        """
        # 计算相关性矩阵
        corr = df.select_dtypes(include=[np.number]).corr()

        # 生成热力图
        fig = go.Figure(
            data=go.Heatmap(
                z=corr.values,
                x=corr.columns,
                y=corr.columns,
                colorscale="RdBu",
                zmin=-1,
                zmax=1,
            )
        )

        fig.update_layout(
            template=self.theme,
            height=self.default_height,
            width=self.default_width,
            title="Feature Correlation Matrix",
        )

        if save_path:
            fig.write_html(save_path)

        return fig

    def plot_feature_importance(
        self, importance_dict: Dict[str, float], save_path: Optional[str] = None
    ) -> go.Figure:
        """生成特征重要性图

        Args:
            importance_dict: 特征重要性字典
            save_path: 保存路径

        Returns:
            go.Figure: Plotly图形对象
        """
        features = list(importance_dict.keys())
        scores = list(importance_dict.values())

        fig = go.Figure(data=[go.Bar(x=scores, y=features, orientation="h")])

        fig.update_layout(
            template=self.theme,
            height=self.default_height,
            width=self.default_width,
            title="Feature Importance",
            xaxis_title="Importance Score",
            yaxis_title="Feature",
        )

        if save_path:
            fig.write_html(save_path)

        return fig

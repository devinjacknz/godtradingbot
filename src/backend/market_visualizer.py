import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class MarketVisualizer:
    """市场数据可视化类"""

    def __init__(
        self,
        output_dir: str = "visualization/market",
        theme: str = "light",
        default_height: int = 800,
        default_width: int = 1200,
        auto_save: bool = True,
    ):
        self.output_dir = Path(output_dir)
        self.theme = theme
        self.default_height = default_height
        self.default_width = default_width
        self.auto_save = auto_save
        self.logger = logging.getLogger(__name__)

        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 设置主题样式
        self.color_scheme = self._get_color_scheme()

    def create_market_overview(
        self,
        market_data: pd.DataFrame,
        indicators: Optional[List[str]] = None,
        save_html: bool = True,
    ) -> go.Figure:
        """创建市场概览图"""
        try:
            # 创建子图
            fig = make_subplots(
                rows=3,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,
                row_heights=[0.6, 0.2, 0.2],
                subplot_titles=("Price & Indicators", "Volume", "Technical"),
            )

            # 添加K线图
            self._add_candlestick(fig, market_data, row=1, col=1)

            # 添加技术指标
            if indicators:
                self._add_technical_indicators(
                    fig, market_data, indicators, row=1, col=1
                )

            # 添加成交量
            self._add_volume(fig, market_data, row=2, col=1)

            # 添加MACD
            self._add_macd(fig, market_data, row=3, col=1)

            # 更新布局
            fig.update_layout(
                title="Market Overview",
                height=self.default_height,
                width=self.default_width,
                showlegend=True,
                template="plotly_white" if self.theme == "light" else "plotly_dark",
            )

            # 保存图表
            if save_html and self.auto_save:
                output_path = (
                    self.output_dir
                    / f"market_overview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                )
                fig.write_html(output_path)

            return fig

        except Exception as e:
            self.logger.error(f"创建市场概览图失败: {str(e)}")
            raise

    def create_depth_chart(
        self, order_book: Dict[str, pd.DataFrame], save_html: bool = True
    ) -> go.Figure:
        """创建深度图"""
        try:
            fig = go.Figure()

            # 添加买单深度
            bids_df = order_book["bids"]
            fig.add_trace(
                go.Scatter(
                    x=bids_df["price"],
                    y=bids_df["cumulative_size"],
                    name="Bids",
                    line=dict(color=self.color_scheme["bid"]),
                    fill="tonexty",
                )
            )

            # 添加卖单深度
            asks_df = order_book["asks"]
            fig.add_trace(
                go.Scatter(
                    x=asks_df["price"],
                    y=asks_df["cumulative_size"],
                    name="Asks",
                    line=dict(color=self.color_scheme["ask"]),
                    fill="tonexty",
                )
            )

            # 更新布局
            fig.update_layout(
                title="Market Depth",
                xaxis_title="Price",
                yaxis_title="Cumulative Size",
                height=self.default_height // 2,
                width=self.default_width,
                showlegend=True,
                template="plotly_white" if self.theme == "light" else "plotly_dark",
            )

            # 保存图表
            if save_html and self.auto_save:
                output_path = (
                    self.output_dir
                    / f"depth_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                )
                fig.write_html(output_path)

            return fig

        except Exception as e:
            self.logger.error(f"创建深度图失败: {str(e)}")
            raise

    def create_technical_dashboard(
        self, market_data: pd.DataFrame, save_html: bool = True
    ) -> go.Figure:
        """创建技术分析仪表板"""
        try:
            # 创建子图
            fig = make_subplots(
                rows=4,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,
                subplot_titles=("Price & MA", "RSI", "MACD", "Bollinger Bands"),
            )

            # 添加价格和均线
            self._add_price_ma(fig, market_data, row=1, col=1)

            # 添加RSI
            self._add_rsi(fig, market_data, row=2, col=1)

            # 添加MACD
            self._add_macd(fig, market_data, row=3, col=1)

            # 添加布林带
            self._add_bollinger_bands(fig, market_data, row=4, col=1)

            # 更新布局
            fig.update_layout(
                title="Technical Analysis Dashboard",
                height=self.default_height * 1.5,
                width=self.default_width,
                showlegend=True,
            )

            # 保存图表
            if save_html and self.auto_save:
                output_path = (
                    self.output_dir
                    / f"technical_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                )
                fig.write_html(output_path)

            return fig

        except Exception as e:
            self.logger.error(f"创建技术分析仪表板失败: {str(e)}")
            raise

    def create_correlation_matrix(
        self, market_data: Dict[str, pd.DataFrame], save_html: bool = True
    ) -> go.Figure:
        """创建相关性矩阵"""
        try:
            # 计算收益率
            returns = pd.DataFrame()
            for symbol, data in market_data.items():
                returns[symbol] = data["close"].pct_change()

            # 计算相关性矩阵
            corr_matrix = returns.corr()

            # 创建热力图
            fig = go.Figure(
                data=go.Heatmap(
                    z=corr_matrix.values,
                    x=corr_matrix.columns,
                    y=corr_matrix.columns,
                    colorscale="RdBu",
                    zmid=0,
                    text=np.round(corr_matrix.values, 2),
                    texttemplate="%{text}",
                    textfont={"size": 10},
                    hoverongaps=False,
                )
            )

            # 更新布局
            fig.update_layout(
                title="Asset Correlation Matrix",
                height=self.default_height // 2,
                width=self.default_width,
                template="plotly_white" if self.theme == "light" else "plotly_dark",
            )

            # 保存图表
            if save_html and self.auto_save:
                output_path = (
                    self.output_dir
                    / f"correlation_matrix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                )
                fig.write_html(output_path)

            return fig

        except Exception as e:
            self.logger.error(f"创建相关性矩阵失败: {str(e)}")
            raise

    def _get_color_scheme(self) -> Dict[str, str]:
        """获取颜色方案"""
        if self.theme == "dark":
            return {
                "up": "#00ff00",
                "down": "#ff0000",
                "volume": "#1f77b4",
                "ma5": "#2ca02c",
                "ma10": "#ff7f0e",
                "ma20": "#d62728",
                "signal": "#9467bd",
                "bid": "#00ff00",
                "ask": "#ff0000",
                "band": "#7f7f7f",
            }
        else:
            return {
                "up": "#26a69a",
                "down": "#ef5350",
                "volume": "#1f77b4",
                "ma5": "#2ca02c",
                "ma10": "#ff7f0e",
                "ma20": "#d62728",
                "signal": "#9467bd",
                "bid": "#26a69a",
                "ask": "#ef5350",
                "band": "#7f7f7f",
            }

    def _add_candlestick(
        self, fig: go.Figure, data: pd.DataFrame, row: int = 1, col: int = 1
    ):
        """添加K线图"""
        fig.add_trace(
            go.Candlestick(
                x=data.index,
                open=data["open"],
                high=data["high"],
                low=data["low"],
                close=data["close"],
                increasing_line_color=self.color_scheme["up"],
                decreasing_line_color=self.color_scheme["down"],
                name="Price",
            ),
            row=row,
            col=col,
        )

    def _add_volume(
        self, fig: go.Figure, data: pd.DataFrame, row: int = 1, col: int = 1
    ):
        """添加成交量"""
        colors = np.where(
            data["close"] >= data["open"],
            self.color_scheme["up"],
            self.color_scheme["down"],
        )

        fig.add_trace(
            go.Bar(x=data.index, y=data["volume"], marker_color=colors, name="Volume"),
            row=row,
            col=col,
        )

    def _add_technical_indicators(
        self,
        fig: go.Figure,
        data: pd.DataFrame,
        indicators: List[str],
        row: int = 1,
        col: int = 1,
    ):
        """添加技术指标"""
        for indicator in indicators:
            if indicator == "MA":
                self._add_moving_averages(fig, data, row, col)
            elif indicator == "BB":
                self._add_bollinger_bands(fig, data, row, col)
            elif indicator == "RSI":
                self._add_rsi(fig, data, row, col)

    def _add_moving_averages(
        self, fig: go.Figure, data: pd.DataFrame, row: int = 1, col: int = 1
    ):
        """添加移动平均线"""
        # 计算移动平均
        ma5 = data["close"].rolling(window=5).mean()
        ma10 = data["close"].rolling(window=10).mean()
        ma20 = data["close"].rolling(window=20).mean()

        # 添加到图表
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=ma5,
                name="MA5",
                line=dict(color=self.color_scheme["ma5"]),
            ),
            row=row,
            col=col,
        )

        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=ma10,
                name="MA10",
                line=dict(color=self.color_scheme["ma10"]),
            ),
            row=row,
            col=col,
        )

        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=ma20,
                name="MA20",
                line=dict(color=self.color_scheme["ma20"]),
            ),
            row=row,
            col=col,
        )

    def _add_bollinger_bands(
        self, fig: go.Figure, data: pd.DataFrame, row: int = 1, col: int = 1
    ):
        """添加布林带"""
        # 计算布林带
        ma20 = data["close"].rolling(window=20).mean()
        std20 = data["close"].rolling(window=20).std()
        upper_band = ma20 + (std20 * 2)
        lower_band = ma20 - (std20 * 2)

        # 添加到图表
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=upper_band,
                name="BB Upper",
                line=dict(color=self.color_scheme["band"], dash="dash"),
            ),
            row=row,
            col=col,
        )

        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=ma20,
                name="BB Middle",
                line=dict(color=self.color_scheme["band"]),
            ),
            row=row,
            col=col,
        )

        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=lower_band,
                name="BB Lower",
                line=dict(color=self.color_scheme["band"], dash="dash"),
                fill="tonexty",
            ),
            row=row,
            col=col,
        )

    def _add_rsi(
        self,
        fig: go.Figure,
        data: pd.DataFrame,
        row: int = 1,
        col: int = 1,
        period: int = 14,
    ):
        """添加RSI指标"""
        # 计算RSI
        delta = data["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # 添加到图表
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=rsi,
                name="RSI",
                line=dict(color=self.color_scheme["signal"]),
            ),
            row=row,
            col=col,
        )

        # 添加参考线
        fig.add_hline(y=70, line_dash="dash", line_color="gray", row=row, col=col)

        fig.add_hline(y=30, line_dash="dash", line_color="gray", row=row, col=col)

    def _add_macd(self, fig: go.Figure, data: pd.DataFrame, row: int = 1, col: int = 1):
        """添加MACD指标"""
        # 计算MACD
        exp1 = data["close"].ewm(span=12, adjust=False).mean()
        exp2 = data["close"].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal

        # 添加到图表
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=macd,
                name="MACD",
                line=dict(color=self.color_scheme["ma5"]),
            ),
            row=row,
            col=col,
        )

        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=signal,
                name="Signal",
                line=dict(color=self.color_scheme["signal"]),
            ),
            row=row,
            col=col,
        )

        # 添加直方图
        colors = np.where(
            histogram >= 0, self.color_scheme["up"], self.color_scheme["down"]
        )

        fig.add_trace(
            go.Bar(x=data.index, y=histogram, name="Histogram", marker_color=colors),
            row=row,
            col=col,
        )

    def _add_price_ma(
        self, fig: go.Figure, data: pd.DataFrame, row: int = 1, col: int = 1
    ):
        """添加价格和均线"""
        # 添加价格
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data["close"],
                name="Price",
                line=dict(color=self.color_scheme["signal"]),
            ),
            row=row,
            col=col,
        )

        # 添加均线
        self._add_moving_averages(fig, data, row, col)

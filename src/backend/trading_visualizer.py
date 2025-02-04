import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class TradingVisualizer:
    """交易分析可视化类"""

    def __init__(
        self,
        output_dir: str = "visualization/trading",
        theme: str = "light",
        default_height: int = 600,
        default_width: int = 1000,
    ):
        self.output_dir = Path(output_dir)
        self.theme = theme
        self.default_height = default_height
        self.default_width = default_width
        self.logger = logging.getLogger(__name__)

        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 设置主题样式
        self.color_scheme = self._get_color_scheme()

    def create_performance_dashboard(
        self,
        trading_data: pd.DataFrame,
        metrics: Dict[str, float],
        time_range: str = "1m",
        save_html: bool = True,
    ) -> go.Figure:
        """创建交易性能仪表板"""
        try:
            # 创建子图
            fig = make_subplots(
                rows=3,
                cols=2,
                subplot_titles=(
                    "Equity Curve",
                    "Drawdown",
                    "Monthly Returns",
                    "Win/Loss Distribution",
                    "Position Duration",
                    "Return Distribution",
                ),
                vertical_spacing=0.1,
                horizontal_spacing=0.1,
            )

            # 添加权益曲线
            self._add_equity_curve(fig, trading_data, row=1, col=1)

            # 添加回撤曲线
            self._add_drawdown_curve(fig, trading_data, row=1, col=2)

            # 添加月度收益热图
            self._add_monthly_returns(fig, trading_data, row=2, col=1)

            # 添加胜负分布
            self._add_win_loss_distribution(fig, trading_data, row=2, col=2)

            # 添加持仓时间分布
            self._add_position_duration(fig, trading_data, row=3, col=1)

            # 添加收益分布
            self._add_return_distribution(fig, trading_data, row=3, col=2)

            # 更新布局
            fig.update_layout(
                title=dict(text="Trading Performance Dashboard", x=0.5, y=0.95),
                height=self.default_height * 2,
                width=self.default_width,
                showlegend=True,
                template="plotly_white" if self.theme == "light" else "plotly_dark",
            )

            # 添加性能指标注释
            self._add_metrics_annotations(fig, metrics)

            # 保存图表
            if save_html:
                output_path = (
                    self.output_dir
                    / f"performance_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                )
                fig.write_html(output_path)

            return fig

        except Exception as e:
            self.logger.error(f"创建交易性能仪表板失败: {str(e)}")
            raise

    def create_trade_analysis(
        self, trades: pd.DataFrame, market_data: pd.DataFrame, save_html: bool = True
    ) -> go.Figure:
        """创建交易分析图表"""
        try:
            # 创建子图
            fig = make_subplots(
                rows=2,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,
                row_heights=[0.7, 0.3],
                subplot_titles=("Price & Trades", "Trade Size & P&L"),
            )

            # 添加价格图表
            fig.add_trace(
                go.Candlestick(
                    x=market_data.index,
                    open=market_data["open"],
                    high=market_data["high"],
                    low=market_data["low"],
                    close=market_data["close"],
                    name="Price",
                ),
                row=1,
                col=1,
            )

            # 添加交易点位
            self._add_trade_markers(fig, trades, row=1, col=1)

            # 添加交易规模和盈亏
            self._add_trade_pnl(fig, trades, row=2, col=1)

            # 更新布局
            fig.update_layout(
                title="Trade Analysis",
                height=self.default_height,
                width=self.default_width,
                showlegend=True,
                xaxis_rangeslider_visible=False,
            )

            # 保存图表
            if save_html:
                output_path = (
                    self.output_dir
                    / f"trade_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                )
                fig.write_html(output_path)

            return fig

        except Exception as e:
            self.logger.error(f"创建交易分析图表失败: {str(e)}")
            raise

    def create_risk_analysis(
        self,
        trading_data: pd.DataFrame,
        risk_metrics: Dict[str, float],
        save_html: bool = True,
    ) -> go.Figure:
        """创建风险分析图表"""
        try:
            # 创建子图
            fig = make_subplots(
                rows=2,
                cols=2,
                subplot_titles=(
                    "Value at Risk",
                    "Risk-Return Scatter",
                    "Rolling Sharpe Ratio",
                    "Risk Contribution",
                ),
            )

            # 添加VaR分析
            self._add_var_analysis(fig, trading_data, row=1, col=1)

            # 添加风险收益散点图
            self._add_risk_return_scatter(fig, trading_data, row=1, col=2)

            # 添加滚动夏普比率
            self._add_rolling_sharpe(fig, trading_data, row=2, col=1)

            # 添加风险贡献分析
            self._add_risk_contribution(fig, trading_data, row=2, col=2)

            # 更新布局
            fig.update_layout(
                title="Risk Analysis",
                height=self.default_height * 1.5,
                width=self.default_width,
                showlegend=True,
            )

            # 添加风险指标注释
            self._add_risk_metrics_annotations(fig, risk_metrics)

            # 保存图表
            if save_html:
                output_path = (
                    self.output_dir
                    / f"risk_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                )
                fig.write_html(output_path)

            return fig

        except Exception as e:
            self.logger.error(f"创建风险分析图表失败: {str(e)}")
            raise

    def _get_color_scheme(self) -> Dict[str, str]:
        """获取颜色方案"""
        if self.theme == "dark":
            return {
                "profit": "#00ff00",
                "loss": "#ff0000",
                "neutral": "#888888",
                "line": "#ffffff",
                "fill": "#1e1e1e",
                "bar_positive": "#00c853",
                "bar_negative": "#ff1744",
            }
        else:
            return {
                "profit": "#00c853",
                "loss": "#ff1744",
                "neutral": "#9e9e9e",
                "line": "#000000",
                "fill": "#f5f5f5",
                "bar_positive": "#4caf50",
                "bar_negative": "#f44336",
            }

    def _add_equity_curve(
        self, fig: go.Figure, data: pd.DataFrame, row: int = 1, col: int = 1
    ):
        """添加权益曲线"""
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data["equity_curve"],
                name="Equity Curve",
                line=dict(color=self.color_scheme["line"]),
                fill="tozeroy",
                fillcolor=self.color_scheme["fill"],
            ),
            row=row,
            col=col,
        )

    def _add_drawdown_curve(
        self, fig: go.Figure, data: pd.DataFrame, row: int = 1, col: int = 1
    ):
        """添加回撤曲线"""
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data["drawdown"],
                name="Drawdown",
                line=dict(color=self.color_scheme["loss"]),
                fill="tozeroy",
                fillcolor=self.color_scheme["loss"],
            ),
            row=row,
            col=col,
        )

    def _add_monthly_returns(
        self, fig: go.Figure, data: pd.DataFrame, row: int = 1, col: int = 1
    ):
        """添加月度收益热图"""
        # 计算月度收益
        monthly_returns = data["returns"].resample("M").sum().to_frame()
        monthly_returns["year"] = monthly_returns.index.year
        monthly_returns["month"] = monthly_returns.index.month
        pivot = monthly_returns.pivot(index="year", columns="month", values="returns")

        # 添加热图
        fig.add_trace(
            go.Heatmap(
                z=pivot.values,
                x=pivot.columns,
                y=pivot.index,
                colorscale="RdYlGn",
                name="Monthly Returns",
            ),
            row=row,
            col=col,
        )

    def _add_win_loss_distribution(
        self, fig: go.Figure, data: pd.DataFrame, row: int = 1, col: int = 1
    ):
        """添加胜负分布"""
        wins = data[data["returns"] > 0]["returns"]
        losses = data[data["returns"] < 0]["returns"]

        fig.add_trace(
            go.Box(y=wins, name="Wins", marker_color=self.color_scheme["profit"]),
            row=row,
            col=col,
        )

        fig.add_trace(
            go.Box(y=losses, name="Losses", marker_color=self.color_scheme["loss"]),
            row=row,
            col=col,
        )

    def _add_position_duration(
        self, fig: go.Figure, data: pd.DataFrame, row: int = 1, col: int = 1
    ):
        """添加持仓时间分布"""
        durations = data["duration"].dropna()

        fig.add_trace(
            go.Histogram(
                x=durations,
                name="Position Duration",
                marker_color=self.color_scheme["neutral"],
            ),
            row=row,
            col=col,
        )

    def _add_return_distribution(
        self, fig: go.Figure, data: pd.DataFrame, row: int = 1, col: int = 1
    ):
        """添加收益分布"""
        returns = data["returns"].dropna()

        fig.add_trace(
            go.Histogram(
                x=returns, name="Returns", marker_color=self.color_scheme["neutral"]
            ),
            row=row,
            col=col,
        )

        # 添加正态分布拟合
        mu = returns.mean()
        sigma = returns.std()
        x = np.linspace(returns.min(), returns.max(), 100)
        y = (
            1
            / (sigma * np.sqrt(2 * np.pi))
            * np.exp(-((x - mu) ** 2) / (2 * sigma**2))
        )
        y = y * len(returns) * (returns.max() - returns.min()) / 30  # 缩放以匹配直方图

        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                name="Normal Distribution",
                line=dict(color=self.color_scheme["line"]),
            ),
            row=row,
            col=col,
        )

    def _add_trade_markers(
        self, fig: go.Figure, trades: pd.DataFrame, row: int = 1, col: int = 1
    ):
        """添加交易标记"""
        # 添加入场点
        fig.add_trace(
            go.Scatter(
                x=trades["entry_time"],
                y=trades["entry_price"],
                mode="markers",
                name="Entry",
                marker=dict(
                    symbol="triangle-up", size=10, color=self.color_scheme["profit"]
                ),
            ),
            row=row,
            col=col,
        )

        # 添加出场点
        fig.add_trace(
            go.Scatter(
                x=trades["exit_time"],
                y=trades["exit_price"],
                mode="markers",
                name="Exit",
                marker=dict(
                    symbol="triangle-down", size=10, color=self.color_scheme["loss"]
                ),
            ),
            row=row,
            col=col,
        )

    def _add_trade_pnl(
        self, fig: go.Figure, trades: pd.DataFrame, row: int = 1, col: int = 1
    ):
        """添加交易盈亏"""
        colors = np.where(
            trades["pnl"] >= 0,
            self.color_scheme["bar_positive"],
            self.color_scheme["bar_negative"],
        )

        fig.add_trace(
            go.Bar(
                x=trades["exit_time"], y=trades["pnl"], name="P&L", marker_color=colors
            ),
            row=row,
            col=col,
        )

    def _add_metrics_annotations(self, fig: go.Figure, metrics: Dict[str, float]):
        """添加性能指标注释"""
        annotations = []
        y_position = 1.05
        x_positions = [0.2, 0.4, 0.6, 0.8]

        for (metric, value), x_pos in zip(metrics.items(), x_positions):
            annotations.append(
                dict(
                    text=f"{metric}: {value:.2%}",
                    x=x_pos,
                    y=y_position,
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                    font=dict(size=12),
                )
            )

        fig.update_layout(annotations=annotations)

    def _add_risk_metrics_annotations(self, fig: go.Figure, metrics: Dict[str, float]):
        """添加风险指标注释"""
        annotations = []
        y_position = 1.05
        x_positions = [0.2, 0.4, 0.6, 0.8]

        for (metric, value), x_pos in zip(metrics.items(), x_positions):
            annotations.append(
                dict(
                    text=f"{metric}: {value:.2f}",
                    x=x_pos,
                    y=y_position,
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                    font=dict(size=12),
                )
            )

        fig.update_layout(annotations=annotations)

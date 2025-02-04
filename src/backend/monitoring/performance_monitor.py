import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import aiohttp
import aioping
import asyncpg
import psutil
from prometheus_client import Counter, Gauge, Histogram, Summary
from datetime import datetime, timedelta


@dataclass
class PerformanceMetrics:
    """Performance metrics for monitoring system"""
    # System metrics
    cpu_usage: Gauge
    memory_usage: Gauge
    network_latency: Histogram
    db_query_time: Histogram
    api_response_time: Histogram
    error_count: Counter
    request_count: Counter

    # Trading metrics
    trade_execution_time: Histogram
    slippage: Histogram
    liquidity_depth: Gauge
    order_book_imbalance: Gauge
    cross_dex_spread: Gauge

    # Meme token metrics
    meme_token_volume: Counter
    meme_token_holders: Gauge
    social_sentiment: Gauge
    viral_coefficient: Gauge

    # Risk metrics
    position_concentration: Gauge
    risk_exposure: Gauge
    volatility: Histogram
    drawdown: Gauge
    critical_alerts: Counter


class PerformanceMonitor:
    """性能监控管理器"""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.db = None
        if "database_url" in config:
            self.db = asyncpg.create_pool(config["database_url"])

        # Initialize metrics
        self.metrics = PerformanceMetrics(
            # System metrics
            cpu_usage=Gauge("system_cpu_usage", "CPU usage percentage"),
            memory_usage=Gauge("system_memory_usage", "Memory usage percentage"),
            network_latency=Histogram("network_latency_seconds", "Network latency"),
            db_query_time=Histogram("db_query_time_seconds", "Database query time"),
            api_response_time=Histogram("api_response_time_seconds", "API response time"),
            error_count=Counter("monitor_error_total", "Total error count", ["type"]),
            request_count=Counter("monitor_request_total", "Total request count", ["endpoint"]),
            
            # Trading metrics
            trade_execution_time=Histogram("trade_execution_time_seconds", "Trade execution time", ["dex"]),
            slippage=Histogram("trade_slippage_percent", "Trade slippage percentage", ["dex", "token_type"]),
            liquidity_depth=Gauge("market_liquidity_depth", "Market liquidity depth", ["dex", "token"]),
            order_book_imbalance=Gauge("order_book_imbalance", "Order book buy/sell imbalance", ["dex", "token"]),
            cross_dex_spread=Gauge("cross_dex_spread_bps", "Spread between DEXs in basis points", ["token_pair"]),
            
            # Meme token metrics
            meme_token_volume=Counter("meme_token_volume", "Meme token trading volume", ["token"]),
            meme_token_holders=Gauge("meme_token_holders", "Number of token holders", ["token"]),
            social_sentiment=Gauge("social_sentiment_score", "Social media sentiment score", ["token"]),
            viral_coefficient=Gauge("viral_coefficient", "Token virality coefficient", ["token"]),
            
            # Risk metrics
            position_concentration=Gauge("position_concentration", "Position concentration percentage", ["token_type"]),
            risk_exposure=Gauge("risk_exposure", "Total risk exposure", ["risk_type"]),
            volatility=Histogram("price_volatility", "Price volatility", ["token", "timeframe"]),
            drawdown=Gauge("max_drawdown", "Maximum drawdown percentage", ["portfolio_type"]),
            critical_alerts=Counter("critical_alerts_total", "Total critical alerts", ["type"])
        )

        # 监控配置
        self.monitor_config = {
            "cpu_threshold": config.get("cpu_threshold", 80),  # CPU使用率阈值
            "memory_threshold": config.get("memory_threshold", 80),  # 内存使用率阈值
            "network_threshold": config.get("network_threshold", 0.1),  # 网络延迟阈值(秒)
            "db_query_threshold": config.get("db_query_threshold", 1.0),  # 数据库查询阈值(秒)
            "api_timeout": config.get("api_timeout", 5.0),  # API超时时间(秒)
            "monitor_interval": config.get("monitor_interval", 60),  # 监控间隔(秒)
            "alert_cooldown": config.get("alert_cooldown", 300),  # 告警冷却时间(秒)
        }

        # 监控任务
        self.monitor_task = None
        self.last_alert_time = {}

    async def start(self):
        """启动监控"""
        self.monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """停止监控"""
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self):
        """监控循环"""
        while True:
            try:
                # 系统资源监控
                await self._monitor_system_resources()

                # 网络延迟监控
                await self._monitor_network_latency()

                # 数据库性能监控
                await self._monitor_database_performance()

                # API性能监控
                await self._monitor_api_performance()

                # 等待下一次监控
                await asyncio.sleep(self.monitor_config["monitor_interval"])

            except Exception as e:
                self.logger.error(f"Monitoring error: {str(e)}")
                self.metrics.error_count.inc()
                await asyncio.sleep(60)

    async def _monitor_system_resources(self):
        """Monitor system resources with enhanced metrics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            self.metrics.cpu_usage.set(cpu_percent)

            if cpu_percent > self.monitor_config["cpu_threshold"]:
                await self._create_alert(
                    "high_cpu_usage", 
                    f"CPU usage: {cpu_percent}%",
                    severity="WARNING" if cpu_percent < 90 else "CRITICAL",
                    metadata={
                        "current_usage": cpu_percent,
                        "threshold": self.monitor_config["cpu_threshold"],
                        "load_avg": os.getloadavg()
                    }
                )

            memory = psutil.virtual_memory()
            self.metrics.memory_usage.set(memory.percent)

            if memory.percent > self.monitor_config["memory_threshold"]:
                await self._create_alert(
                    "high_memory_usage", 
                    f"Memory usage: {memory.percent}%",
                    severity="WARNING" if memory.percent < 90 else "CRITICAL",
                    metadata={
                        "current_usage": memory.percent,
                        "threshold": self.monitor_config["memory_threshold"],
                        "available": memory.available,
                        "total": memory.total
                    }
                )

        except Exception as e:
            self.logger.error(f"System resource monitoring error: {str(e)}")
            self.metrics.error_count.inc()

    async def _monitor_network_latency(self):
        """监控网络延迟"""
        try:
            # 测试关键服务延迟
            for service in self.config.get("network_services", []):
                try:
                    start_time = time.time()
                    delay = await aioping.ping(service["host"])
                    self.metrics.network_latency.observe(delay)

                    if delay > self.monitor_config["network_threshold"]:
                        await self._create_alert(
                            "high_network_latency",
                            f"High latency to {service['host']}: {delay:.3f}s",
                        )

                except Exception as e:
                    self.logger.error(
                        f"Network latency check error for {service['host']}: {str(e)}"
                    )
                    self.metrics.error_count.inc()

        except Exception as e:
            self.logger.error(f"Network monitoring error: {str(e)}")
            self.metrics.error_count.inc()

    async def _monitor_database_performance(self):
        """监控数据库性能"""
        try:
            # 连接数据库
            conn = await asyncpg.connect(self.config["database_url"])

            try:
                # 测试查询性能
                start_time = time.time()
                await conn.fetch("SELECT 1")
                query_time = time.time() - start_time

                self.metrics.db_query_time.observe(query_time)

                if query_time > self.monitor_config["db_query_threshold"]:
                    await self._create_alert(
                        "slow_database", f"Slow database response: {query_time:.3f}s"
                    )

                # 检查数据库状态
                status = await conn.fetch(
                    """
                    SELECT * FROM pg_stat_activity
                    WHERE state = 'active'
                """
                )

                # 分析长时间运行的查询
                for record in status:
                    if record["state_change"] < datetime.now() - timedelta(minutes=5):
                        await self._create_alert(
                            "long_running_query",
                            f"Long running query detected: {record['query']}",
                        )

            finally:
                await conn.close()

        except Exception as e:
            self.logger.error(f"Database monitoring error: {str(e)}")
            self.metrics.error_count.inc()

    async def _monitor_api_performance(self):
        """Monitor API performance with focus on DEX and meme token endpoints"""
        try:
            async with aiohttp.ClientSession() as session:
                # Monitor DEX endpoints
                for dex in self.config.get("dex_endpoints", []):
                    try:
                        # Monitor liquidity endpoints
                        start_time = time.time()
                        async with session.get(
                            dex["liquidity_url"],
                            timeout=self.monitor_config["api_timeout"]
                        ) as response:
                            response_time = time.time() - start_time
                            self.metrics.api_response_time.labels(endpoint="liquidity").observe(response_time)
                            self.metrics.trade_execution_time.labels(dex=dex["name"]).observe(response_time)

                            if response.status == 200:
                                data = await response.json()
                                self.metrics.liquidity_depth.labels(
                                    dex=dex["name"],
                                    token=data.get("token", "unknown")
                                ).set(float(data.get("depth", 0)))
                            
                            if response_time > dex.get("threshold", 1.0):
                                await self._create_alert(
                                    "slow_dex_response",
                                    f"Slow DEX response from {dex['name']}: {response_time:.3f}s"
                                )

                        # Monitor order book endpoints
                        start_time = time.time()
                        async with session.get(
                            dex["orderbook_url"],
                            timeout=self.monitor_config["api_timeout"]
                        ) as response:
                            response_time = time.time() - start_time
                            self.metrics.api_response_time.labels(endpoint="orderbook").observe(response_time)

                            if response.status == 200:
                                data = await response.json()
                                self.metrics.order_book_imbalance.labels(
                                    dex=dex["name"],
                                    token=data.get("token", "unknown")
                                ).set(float(data.get("imbalance", 0)))

                    except Exception as e:
                        self.logger.error(f"DEX monitoring error for {dex['name']}: {str(e)}")
                        self.metrics.error_count.labels(type="dex_api").inc()

                # Monitor meme token endpoints
                for endpoint in self.config.get("meme_token_endpoints", []):
                    try:
                        start_time = time.time()
                        async with session.get(
                            endpoint["url"],
                            timeout=self.monitor_config["api_timeout"]
                        ) as response:
                            response_time = time.time() - start_time
                            self.metrics.api_response_time.labels(endpoint="meme_data").observe(response_time)

                            if response.status == 200:
                                data = await response.json()
                                token = data.get("token", "unknown")
                                
                                # Update meme token metrics
                                self.metrics.meme_token_volume.labels(token=token).inc(float(data.get("volume", 0)))
                                self.metrics.meme_token_holders.labels(token=token).set(float(data.get("holders", 0)))
                                self.metrics.social_sentiment.labels(token=token).set(float(data.get("sentiment", 0)))
                                self.metrics.viral_coefficient.labels(token=token).set(float(data.get("virality", 0)))

                            if response.status >= 400:
                                await self._create_alert(
                                    "meme_data_error",
                                    f"Meme token data error for {endpoint['url']}: {response.status}"
                                )

                    except Exception as e:
                        self.logger.error(f"Meme token monitoring error: {str(e)}")
                        self.metrics.error_count.labels(type="meme_api").inc()

                # Monitor cross-DEX metrics
                await self._monitor_cross_dex_metrics(session)

        except Exception as e:
            self.logger.error(f"API monitoring error: {str(e)}")
            self.metrics.error_count.labels(type="general").inc()

    async def _monitor_cross_dex_metrics(self, session: aiohttp.ClientSession):
        """Monitor cross-DEX metrics for arbitrage opportunities with enhanced tracking"""
        try:
            for pair in self.config.get("token_pairs", []):
                prices = {}
                volumes = {}
                liquidity = {}
                error_counts = {}
                
                for dex in self.config.get("dex_endpoints", []):
                    try:
                        async with session.get(
                            f"{dex['price_url']}/{pair}",
                            timeout=self.monitor_config["api_timeout"]
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                prices[dex["name"]] = float(data.get("price", 0))
                                volumes[dex["name"]] = float(data.get("volume_24h", 0))
                                liquidity[dex["name"]] = float(data.get("liquidity", 0))
                                
                                # Track individual DEX metrics
                                self.metrics.liquidity_depth.labels(
                                    dex=dex["name"],
                                    token=pair
                                ).set(float(data.get("liquidity", 0)))
                                
                                self.metrics.meme_token_volume.labels(
                                    token=pair
                                ).inc(float(data.get("volume_24h", 0)))
                            else:
                                error_counts[dex["name"]] = error_counts.get(dex["name"], 0) + 1
                                self.metrics.error_count.labels(type="dex_api").inc()
                                
                    except Exception as e:
                        self.logger.error(f"Error fetching {dex['name']} metrics: {str(e)}")
                        error_counts[dex["name"]] = error_counts.get(dex["name"], 0) + 1
                        self.metrics.error_count.labels(type="dex_api").inc()
                        continue

                if len(prices) >= 2:
                    max_price = max(prices.values())
                    min_price = min(prices.values())
                    if min_price > 0:
                        spread_bps = (max_price - min_price) / min_price * 10000
                        self.metrics.cross_dex_spread.labels(token_pair=pair).set(spread_bps)
                        
                        total_volume = sum(volumes.values())
                        total_liquidity = sum(liquidity.values())
                        
                        # Calculate liquidity distribution score
                        max_liquidity = max(liquidity.values()) if liquidity else 0
                        min_liquidity = min(liquidity.values()) if liquidity else 0
                        liquidity_distribution = min_liquidity / max_liquidity if max_liquidity > 0 else 0
                        
                        # Determine alert severity based on multiple factors
                        alert_severity = "WARNING"
                        if spread_bps > self.config.get("critical_spread_bps", 200):
                            alert_severity = "CRITICAL"
                        elif spread_bps > self.config.get("max_spread_bps", 100):
                            if liquidity_distribution < 0.3 or total_volume < self.config.get("min_volume", 1000):
                                alert_severity = "CRITICAL"
                            
                        if spread_bps > self.config.get("max_spread_bps", 100):
                            await self._create_alert(
                                "high_cross_dex_spread",
                                f"High spread detected for {pair}: {spread_bps:.2f} bps",
                                severity=alert_severity,
                                metadata={
                                    "spread_bps": spread_bps,
                                    "prices": prices,
                                    "total_volume_24h": total_volume,
                                    "total_liquidity": total_liquidity,
                                    "volume_distribution": volumes,
                                    "liquidity_distribution": liquidity,
                                    "error_counts": error_counts,
                                    "liquidity_score": liquidity_distribution
                                }
                            )

        except Exception as e:
            self.logger.error(f"Cross-DEX monitoring error: {str(e)}")
            self.metrics.error_count.labels(type="cross_dex").inc()

    async def _create_alert(self, alert_type: str, message: str, severity: str = "WARNING", metadata: Optional[Dict[str, Any]] = None):
        """Create alert with severity level and metadata"""
        current_time = time.time()

        if alert_type in self.last_alert_time:
            if current_time - self.last_alert_time[alert_type] < self.monitor_config["alert_cooldown"]:
                return

        self.last_alert_time[alert_type] = current_time
        
        if severity not in ["INFO", "WARNING", "ERROR", "CRITICAL"]:
            severity = "WARNING"
            
        alert_data = {
            "type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "source": "performance_monitor",
            "status": "ACTIVE"
        }
            
        log_level = getattr(logging, severity, logging.WARNING)
        self.logger.log(log_level, f"Alert [{severity}]: {message}")
        
        if severity in ["ERROR", "CRITICAL"]:
            self.metrics.error_count.labels(type=alert_type).inc()
            await self._route_critical_alert(alert_data)
            
        return alert_data

    def _get_percentile(self, metric: Histogram, percentile: float) -> float:
        """Get percentile value from histogram metric"""
        try:
            return float(metric._sum.get() * percentile / metric._count.get()) if metric._count.get() > 0 else 0.0
        except Exception:
            return 0.0

    def _get_max(self, metric: Histogram) -> float:
        """Get maximum value from histogram metric"""
        try:
            return float(metric._sum.get()) if metric._count.get() > 0 else 0.0
        except Exception:
            return 0.0

    def _get_moving_average(self, metric: Gauge, hours: int = 24) -> float:
        """Calculate exponential moving average for a metric"""
        try:
            current = float(metric._value.get())
            if not hasattr(self, '_metric_history'):
                self._metric_history = {}
            
            metric_key = f"{metric._name}_{hours}"
            if metric_key not in self._metric_history:
                self._metric_history[metric_key] = []
                
            history = self._metric_history[metric_key]
            history.append((time.time(), current))
            
            # Keep only last 24 hours of data
            cutoff = time.time() - hours * 3600
            history = [(t, v) for t, v in history if t > cutoff]
            self._metric_history[metric_key] = history
            
            if not history:
                return current
                
            # Calculate EMA with more weight on recent values
            alpha = 2.0 / (len(history) + 1)
            ema = history[0][1]
            for _, value in history[1:]:
                ema = alpha * value + (1 - alpha) * ema
                
            return ema
        except Exception as e:
            self.logger.error(f"Error calculating moving average: {str(e)}")
            return 0.0

    def _get_volume_change(self, token: str, hours: int = 24) -> float:
        """Calculate volume change percentage with trend analysis"""
        try:
            current = float(self.metrics.meme_token_volume.labels(token=token)._value.get())
            avg = self._get_moving_average(self.metrics.meme_token_volume.labels(token=token), hours)
            
            if avg > 0:
                change = (current - avg) / avg
                # Apply volatility adjustment
                volatility = self._get_token_volatility(token)
                if volatility > 0:
                    change = change / volatility
                return change
            return 0.0
        except Exception as e:
            self.logger.error(f"Error calculating volume change for {token}: {str(e)}")
            return 0.0

    def _get_volume_trend(self, token: str) -> str:
        """Get volume trend direction with momentum analysis"""
        try:
            short_change = self._get_volume_change(token, hours=4)
            long_change = self._get_volume_change(token, hours=24)
            
            # Calculate trend strength
            trend_strength = abs(short_change - long_change)
            
            if trend_strength < 0.05:
                return "stable"
                
            if short_change > long_change:
                return "accelerating" if trend_strength > 0.2 else "increasing"
            else:
                return "declining" if trend_strength > 0.2 else "decreasing"
        except Exception as e:
            self.logger.error(f"Error analyzing volume trend for {token}: {str(e)}")
            return "unknown"

    def _get_holder_change(self, token: str, hours: int = 24) -> float:
        """Calculate holder count change"""
        try:
            current = float(self.metrics.meme_token_holders.labels(token=token)._value.get())
            return current
        except Exception:
            return 0.0

    def _get_sentiment_change(self, token: str, hours: int = 24) -> float:
        """Calculate sentiment change"""
        try:
            current = float(self.metrics.social_sentiment.labels(token=token)._value.get())
            return current
        except Exception:
            return 0.0

    def _get_virality_trend(self, token: str) -> str:
        """Get virality coefficient trend"""
        try:
            current = float(self.metrics.viral_coefficient.labels(token=token)._value.get())
            if current > 1.5:
                return "viral"
            elif current > 1.0:
                return "growing"
            return "stable"
        except Exception:
            return "unknown"

    async def _route_critical_alert(self, alert_data: Dict[str, Any]) -> None:
        """Route critical alerts to appropriate channels with enhanced error tracking"""
        try:
            alert_type = alert_data["type"]
            severity = alert_data["severity"]
            source = alert_data["source"]
            
            self.metrics.critical_alerts.labels(
                type=alert_type,
                severity=severity,
                source=source
            ).inc()
            
            if self.db is not None:
                try:
                    async with self.db.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO alerts (
                                type, message, severity, timestamp, metadata,
                                source, status, retry_count, last_retry
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                            """,
                            alert_data["type"],
                            alert_data["message"],
                            alert_data["severity"],
                            alert_data["timestamp"],
                            alert_data["metadata"],
                            alert_data["source"],
                            alert_data["status"],
                            0,
                            None
                        )
                except Exception as db_error:
                    self.logger.error(f"Database error while routing alert: {str(db_error)}")
                    self.metrics.error_count.labels(type="alert_storage").inc()
                    
                    alert_data["metadata"]["db_error"] = str(db_error)
                    alert_data["status"] = "ERROR"
            
            alert_context = {
                "alert_type": alert_type,
                "severity": severity,
                "source": source,
                "timestamp": alert_data["timestamp"],
                "status": alert_data["status"],
                "metadata": alert_data["metadata"]
            }
            
            self.logger.critical(
                f"Critical alert [{alert_type}] from {source}\n"
                f"Severity: {severity}\n"
                f"Message: {alert_data['message']}\n"
                f"Status: {alert_data['status']}\n"
                f"Context: {alert_context}\n"
                f"Metadata: {alert_data['metadata']}"
            )
            
            if severity == "CRITICAL":
                self.metrics.error_count.labels(
                    type=f"critical_{alert_type}"
                ).inc()
            
        except Exception as e:
            self.logger.error(
                f"Error routing critical alert: {str(e)}\n"
                f"Alert data: {alert_data}"
            )
            self.metrics.error_count.labels(type="alert_routing").inc()

    def _get_token_volatility(self, token: str, window_hours: int = 24) -> float:
        """Calculate token volatility with advanced analysis"""
        try:
            current = float(self.metrics.volatility.labels(token=token, timeframe="1h")._value.get())
            avg = self._get_moving_average(self.metrics.volatility.labels(token=token, timeframe="1h"), window_hours)
            
            if not hasattr(self, '_volatility_history'):
                self._volatility_history = {}
                
            if token not in self._volatility_history:
                self._volatility_history[token] = []
                
            history = self._volatility_history[token]
            history.append((time.time(), current))
            
            cutoff = time.time() - window_hours * 3600
            history = [(t, v) for t, v in history if t > cutoff]
            self._volatility_history[token] = history
            
            if len(history) < 2:
                return current
                
            returns = []
            for i in range(1, len(history)):
                prev_price = history[i-1][1]
                curr_price = history[i][1]
                if prev_price > 0:
                    returns.append(math.log(curr_price / prev_price))
                    
            if returns:
                realized_vol = math.sqrt(sum(r * r for r in returns) / len(returns)) * math.sqrt(24 * 365)
                return 0.7 * realized_vol + 0.3 * current
                
            return current
            
        except Exception as e:
            self.logger.error(f"Error calculating token volatility for {token}: {str(e)}")
            return 0.0

    def _get_liquidity_score(self, token: str) -> float:
        """Calculate comprehensive liquidity score"""
        try:
            depths = {}
            total_volume = 0.0
            
            for dex in self.config.get("dex_list", []):
                try:
                    depth = float(self.metrics.liquidity_depth.labels(dex=dex, token=token)._value.get())
                    volume = float(self.metrics.meme_token_volume.labels(token=token)._value.get())
                    depths[dex] = depth
                    total_volume += volume
                except Exception as e:
                    self.logger.error(f"Error getting liquidity data for {dex}: {str(e)}")
                    
            if not depths:
                return 0.0
                
            total_depth = sum(depths.values())
            avg_depth = total_depth / len(depths)
            
            # Calculate depth distribution score
            max_depth = max(depths.values())
            min_depth = min(depths.values())
            distribution_score = min_depth / max_depth if max_depth > 0 else 0
            
            # Calculate volume-adjusted score
            volume_factor = 1.0
            if total_volume > 0:
                volume_factor = min(1.0, avg_depth / (total_volume * 0.1))
                
            # Get volatility adjustment
            volatility = self._get_token_volatility(token)
            vol_factor = 1.0 / (1.0 + volatility) if volatility > 0 else 1.0
            
            # Combine factors
            base_score = (total_depth * distribution_score) / len(depths)
            return base_score * volume_factor * vol_factor
            
        except Exception as e:
            self.logger.error(f"Error calculating liquidity score for {token}: {str(e)}")
            return 0.0

    def _get_market_impact(self, token: str) -> float:
        """Calculate market impact score"""
        try:
            return 1.0 - self._get_liquidity_score(token)
        except Exception:
            return 1.0

    def _get_concentration_trend(self, token_type: str) -> str:
        """Get position concentration trend"""
        try:
            current = float(self.metrics.position_concentration.labels(token_type=token_type)._value.get())
            limit = self.config.get(f"{token_type}_concentration_limit", 0.2)
            if current > limit * 1.2:
                return "high"
            elif current > limit:
                return "elevated"
            return "normal"
        except Exception:
            return "unknown"

    def _get_exposure_utilization(self, risk_type: str) -> float:
        """Calculate risk exposure utilization"""
        try:
            current = float(self.metrics.risk_exposure.labels(risk_type=risk_type)._value.get())
            limit = self.config.get(f"{risk_type}_exposure_limit", 1.0)
            return current / limit if limit > 0 else 1.0
        except Exception:
            return 0.0

    def _get_volatility_zscore(self, token: str, timeframe: str) -> float:
        """Calculate volatility z-score with historical context"""
        try:
            current = float(self.metrics.volatility.labels(token=token, timeframe=timeframe)._value.get())
            history = self._get_moving_average(self.metrics.volatility.labels(token=token, timeframe=timeframe), hours=24)
            
            if not hasattr(self, '_zscore_history'):
                self._zscore_history = {}
                
            key = f"{token}_{timeframe}"
            if key not in self._zscore_history:
                self._zscore_history[key] = []
                
            scores = self._zscore_history[key]
            scores.append((time.time(), current))
            
            # Keep last 24 hours
            cutoff = time.time() - 24 * 3600
            scores = [(t, v) for t, v in scores if t > cutoff]
            self._zscore_history[key] = scores
            
            if len(scores) < 2:
                return 0.0
                
            values = [v for _, v in scores]
            mean = sum(values) / len(values)
            std = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values)) if len(values) > 1 else 1.0
            
            if std > 0:
                zscore = (current - mean) / std
                # Apply exponential weighting to recent values
                weight = 0.7 * math.exp(-len(scores) / 24) + 0.3
                return zscore * weight
                
            return 0.0
            
        except Exception as e:
            self.logger.error(f"Error calculating volatility z-score for {token}: {str(e)}")
            return 0.0

    def _get_volatility_trend(self, token: str, timeframe: str) -> str:
        """Get volatility trend with momentum analysis"""
        try:
            zscore = self._get_volatility_zscore(token, timeframe)
            current = float(self.metrics.volatility.labels(token=token, timeframe=timeframe)._value.get())
            avg = self._get_moving_average(self.metrics.volatility.labels(token=token, timeframe=timeframe), hours=4)
            
            # Calculate momentum
            momentum = (current - avg) / avg if avg > 0 else 0
            
            # Combine z-score and momentum for trend analysis
            if zscore > 2.0:
                if momentum > 0.1:
                    return "extreme_increasing"
                elif momentum < -0.1:
                    return "extreme_decreasing"
                return "extreme"
            elif zscore > 1.0:
                if momentum > 0.1:
                    return "high_increasing"
                elif momentum < -0.1:
                    return "high_decreasing"
                return "high"
            else:
                if momentum > 0.1:
                    return "normal_increasing"
                elif momentum < -0.1:
                    return "normal_decreasing"
                return "normal"
                
        except Exception as e:
            self.logger.error(f"Error analyzing volatility trend for {token}: {str(e)}")
            return "unknown"

    def _get_max_drawdown(self, portfolio_type: str, hours: int = 24) -> float:
        """Calculate maximum drawdown with historical analysis"""
        try:
            if not hasattr(self, '_portfolio_history'):
                self._portfolio_history = {}
                
            key = f"drawdown_{portfolio_type}"
            if key not in self._portfolio_history:
                self._portfolio_history[key] = []
                
            current = float(self.metrics.drawdown.labels(portfolio_type=portfolio_type)._value.get())
            history = self._portfolio_history[key]
            history.append((time.time(), current))
            
            cutoff = time.time() - hours * 3600
            history = [(t, v) for t, v in history if t > cutoff]
            self._portfolio_history[key] = history
            
            if not history:
                return current
                
            peak = max(v for _, v in history)
            trough = min(v for _, v in history)
            
            if peak <= 0:
                return 0.0
                
            drawdown = (peak - trough) / peak
            return max(drawdown, current)
            
        except Exception as e:
            self.logger.error(f"Error calculating max drawdown for {portfolio_type}: {str(e)}")
            return 0.0

    def _get_drawdown_recovery_time(self, portfolio_type: str) -> int:
        """Estimate drawdown recovery time using trend analysis"""
        try:
            if not hasattr(self, '_recovery_history'):
                self._recovery_history = {}
                
            key = f"recovery_{portfolio_type}"
            if key not in self._recovery_history:
                self._recovery_history[key] = []
                
            current = float(self.metrics.drawdown.labels(portfolio_type=portfolio_type)._value.get())
            history = self._recovery_history[key]
            history.append((time.time(), current))
            
            cutoff = time.time() - 24 * 3600  # Last 24 hours
            history = [(t, v) for t, v in history if t > cutoff]
            self._recovery_history[key] = history
            
            if current <= 0 or len(history) < 2:
                return 0
                
            # Calculate recovery rate using linear regression
            times = [(t - history[0][0])/3600 for t, _ in history]  # Hours since start
            values = [v for _, v in history]
            
            if len(times) < 2:
                return int(current * 24)
                
            # Simple linear regression for recovery rate
            n = len(times)
            sum_x = sum(times)
            sum_y = sum(values)
            sum_xy = sum(x*y for x, y in zip(times, values))
            sum_xx = sum(x*x for x in times)
            
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x)
            
            if slope >= 0:
                return int(current * 24)  # No recovery trend
                
            # Estimate hours until drawdown reaches 0
            recovery_hours = -current / slope if slope < 0 else 24
            return max(1, int(recovery_hours))
            
        except Exception as e:
            self.logger.error(f"Error estimating recovery time for {portfolio_type}: {str(e)}")
            return 0

    def _get_active_risk_alerts(self) -> Dict[str, Dict[str, Any]]:
        """Get active risk alerts with detailed metadata"""
        try:
            alerts: Dict[str, Dict[str, Any]] = {}
            for risk_type in ["market", "liquidity", "volatility"]:
                utilization = self._get_exposure_utilization(risk_type)
                if utilization > 0.8:
                    severity = "CRITICAL" if utilization > 0.95 else "WARNING"
                    alerts[risk_type] = {
                        "level": "high" if utilization > 0.95 else "elevated",
                        "severity": severity,
                        "utilization": utilization,
                        "metadata": {
                            "current_value": utilization,
                            "threshold": 0.8,
                            "risk_type": risk_type,
                            "trend": self._get_concentration_trend(risk_type)
                        }
                    }
            return alerts
        except Exception:
            return {
                "system": {},
                "api": {},
                "trading": {},
                "meme_tokens": {},
                "risk": {"alerts": {}}
            }

    def get_performance_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get performance metrics"""
        try:
            metrics: Dict[str, Dict[str, Any]] = {
                # System metrics
                "system": {
                    "cpu": {
                        "usage": self.metrics.cpu_usage._value.get(),
                        "load_avg": os.getloadavg(),
                        "process_count": len(psutil.pids())
                    },
                    "memory": {
                        "usage": self.metrics.memory_usage._value.get(),
                        "available": psutil.virtual_memory().available,
                        "total": psutil.virtual_memory().total
                    },
                    "network": {
                        "latency": self.metrics.network_latency._sum.get(),
                        "latency_count": self.metrics.network_latency._count.get(),
                        "error_rate": self.metrics.error_count.labels(type="network")._value.get() / max(1, self.metrics.request_count.labels(endpoint="network")._value.get())
                    },
                    "database": {
                        "query_time": self.metrics.db_query_time._sum.get() / max(1, self.metrics.db_query_time._count.get()),
                        "error_rate": self.metrics.error_count.labels(type="database")._value.get() / max(1, self.metrics.request_count.labels(endpoint="database")._value.get())
                    }
                },
                # API performance
                "api": {
                    "response_time": {
                        endpoint: self.metrics.api_response_time.labels(endpoint=endpoint)._sum.get() / max(1, self.metrics.api_response_time.labels(endpoint=endpoint)._count.get())
                        for endpoint in ["liquidity", "orderbook", "meme_data"]
                    },
                    "error_rates": {
                        t: self.metrics.error_count.labels(type=t)._value.get() / max(1, self.metrics.request_count.labels(endpoint=t)._value.get())
                        for t in ["dex_api", "meme_api", "cross_dex"]
                    },
                    "request_counts": {
                        e: self.metrics.request_count.labels(endpoint=e)._value.get()
                        for e in ["liquidity", "orderbook", "meme_data"]
                    }
                },
            
                # Trading performance
                "trading": {
                    "execution": {
                        dex: {
                            "time": {
                                "avg": self.metrics.trade_execution_time.labels(dex=dex)._sum.get() / max(1, self.metrics.trade_execution_time.labels(dex=dex)._count.get()),
                                "p95": self._get_percentile(self.metrics.trade_execution_time.labels(dex=dex), 0.95),
                                "p99": self._get_percentile(self.metrics.trade_execution_time.labels(dex=dex), 0.99)
                            },
                            "slippage": {
                                "standard": {
                                    "avg": self.metrics.slippage.labels(dex=dex, token_type="standard")._sum.get() / max(1, self.metrics.slippage.labels(dex=dex, token_type="standard")._count.get()),
                                    "max": self._get_max(self.metrics.slippage.labels(dex=dex, token_type="standard"))
                                },
                                "meme": {
                                    "avg": self.metrics.slippage.labels(dex=dex, token_type="meme")._sum.get() / max(1, self.metrics.slippage.labels(dex=dex, token_type="meme")._count.get()),
                                    "max": self._get_max(self.metrics.slippage.labels(dex=dex, token_type="meme"))
                                }
                            }
                        }
                        for dex in self.config.get("dex_list", [])
                    },
                    "liquidity": {
                        dex: {
                            "depth": {
                                token: self.metrics.liquidity_depth.labels(dex=dex, token=token)._value.get()
                                for token in self.config.get("tracked_tokens", [])
                            },
                            "imbalance": {
                                token: self.metrics.order_book_imbalance.labels(dex=dex, token=token)._value.get()
                                for token in self.config.get("tracked_tokens", [])
                            }
                        }
                        for dex in self.config.get("dex_list", [])
                    },
                    "cross_dex": {
                        "spreads": {
                            pair: {
                                "current": self.metrics.cross_dex_spread.labels(token_pair=pair)._value.get(),
                                "avg_24h": self._get_moving_average(self.metrics.cross_dex_spread.labels(token_pair=pair), hours=24)
                            }
                            for pair in self.config.get("token_pairs", [])
                        }
                    }
                },
            
                # Meme token analytics
                "meme_tokens": {
                    token: {
                        "volume": {
                            "current": self.metrics.meme_token_volume.labels(token=token)._value.get(),
                            "change_24h": self._get_volume_change(token, hours=24),
                            "trend": self._get_volume_trend(token)
                        },
                        "holders": {
                            "count": self.metrics.meme_token_holders.labels(token=token)._value.get(),
                            "change_24h": self._get_holder_change(token, hours=24)
                        },
                        "social": {
                            "sentiment": self.metrics.social_sentiment.labels(token=token)._value.get(),
                            "sentiment_change": self._get_sentiment_change(token, hours=24),
                            "virality": self.metrics.viral_coefficient.labels(token=token)._value.get(),
                            "virality_trend": self._get_virality_trend(token)
                        },
                        "risk_metrics": {
                            "volatility": self._get_token_volatility(token),
                            "liquidity_score": self._get_liquidity_score(token),
                            "market_impact": self._get_market_impact(token)
                        }
                    }
                    for token in self.config.get("meme_tokens", [])
                },
            
                # Risk analytics
                "risk": {
                    "portfolio": {
                        "concentration": {
                            t: {
                                "current": self.metrics.position_concentration.labels(token_type=t)._value.get(),
                                "limit": self.config.get(f"{t}_concentration_limit", 0.2),
                                "trend": self._get_concentration_trend(t)
                            }
                            for t in ["standard", "meme"]
                        },
                        "exposure": {
                            t: {
                                "value": self.metrics.risk_exposure.labels(risk_type=t)._value.get(),
                                "limit": self.config.get(f"{t}_exposure_limit", 1.0),
                                "utilization": self._get_exposure_utilization(t)
                            }
                            for t in ["market", "liquidity", "volatility"]
                        }
                    },
                    "market": {
                        "volatility": {
                            token: {
                                tf: {
                                    "current": self.metrics.volatility.labels(token=token, timeframe=tf)._value.get(),
                                    "zscore": self._get_volatility_zscore(token, tf),
                                    "trend": self._get_volatility_trend(token, tf)
                                }
                                for tf in ["1h", "4h", "24h"]
                            }
                            for token in self.config.get("tracked_tokens", [])
                        },
                        "drawdown": {
                            pt: {
                                "current": self.metrics.drawdown.labels(portfolio_type=pt)._value.get(),
                                "max_24h": self._get_max_drawdown(pt, hours=24),
                                "recovery_time": self._get_drawdown_recovery_time(pt)
                            }
                            for pt in ["overall", "meme", "standard"]
                        }
                    },
                    "alerts": self._get_active_risk_alerts()
                }
            }
            return metrics
        except Exception as e:
            self.logger.error(f"Error getting performance metrics: {str(e)}")
            return {
                "system": {},
                "api": {},
                "trading": {},
                "meme_tokens": {},
                "risk": {"alerts": []}
            }

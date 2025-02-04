import asyncio
import itertools
import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

import aiohttp
import aioping
import aiosmtplib
import asyncpg
import numpy as np
import psutil
from prometheus_client import Counter, Gauge, Histogram


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertCategory(Enum):
    SYSTEM = "system"
    DEX = "dex"
    MEME = "meme"
    TRADING = "trading"
    RISK = "risk"
    CROSS_DEX = "cross_dex"


class AlertState(Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    ESCALATED = "escalated"
    SUPPRESSED = "suppressed"


@dataclass
class AlertMetrics:
    """告警指标"""

    alert_count: Counter
    active_alerts: Gauge
    alert_duration: Histogram
    recovery_count: Counter
    notification_count: Counter


class AlertManager:
    """告警管理器"""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # 初始化指标
        self.metrics = AlertMetrics(
            alert_count=Counter("alert_total", "Total number of alerts", ["level"]),
            active_alerts=Gauge("active_alerts", "Number of active alerts", ["level"]),
            alert_duration=Histogram("alert_duration_seconds", "Alert duration"),
            recovery_count=Counter(
                "alert_recovery_total", "Number of recovered alerts"
            ),
            notification_count=Counter(
                "alert_notification_total", "Number of notifications sent", ["channel"]
            ),
        )

        # 告警配置
        self.alert_config = {
            "aggregation_window": config.get("aggregation_window", 300),  # 5分钟聚合窗口
            "max_notifications": config.get("max_notifications", 10),  # 每个窗口最大通知数
            "auto_resolve_timeout": config.get("auto_resolve_timeout", 3600),  # 1小时自动解决
            "notification_cooldown": config.get(
                "notification_cooldown", 600
            ),  # 10分钟通知冷却
            "recovery_threshold": config.get("recovery_threshold", 3),  # 恢复阈值次数
        }

        # 告警状态
        self.active_alerts = {}
        self.alert_history = []
        self.notification_history = {}

        # 告警任务
        self.alert_task = None

    async def start(self):
        """启动告警管理器"""
        self.alert_task = asyncio.create_task(self._alert_loop())

    async def stop(self):
        """停止告警管理器"""
        if self.alert_task:
            self.alert_task.cancel()
            try:
                await self.alert_task
            except asyncio.CancelledError:
                pass

    async def _alert_loop(self):
        """告警处理循环"""
        while True:
            try:
                # 检查告警状态
                await self._check_alert_states()

                # 聚合告警
                await self._aggregate_alerts()

                # 发送通知
                await self._send_notifications()

                # 检查自动恢复
                await self._check_auto_recovery()

                # 清理历史数据
                self._cleanup_history()

                # 等待下一次处理
                await asyncio.sleep(60)

            except Exception as e:
                self.logger.error(f"Alert processing error: {str(e)}")
                await asyncio.sleep(60)

    async def create_alert(self, alert_data: Dict):
        """Create alert with enhanced categorization"""
        try:
            alert_id = alert_data.get("id") or str(uuid.uuid4())
            level = AlertLevel(alert_data.get("level", "warning"))
            category = AlertCategory(alert_data.get("category", "system"))

            # Update metrics
            self.metrics.alert_count.labels(level=level.value).inc()
            self.metrics.active_alerts.labels(level=level.value).inc()

            # Create alert record
            alert = {
                "id": alert_id,
                "level": level,
                "category": category,
                "message": alert_data["message"],
                "source": alert_data.get("source", "system"),
                "timestamp": datetime.now(),
                "state": AlertState.ACTIVE,
                "check_count": 0,
                "recovery_count": 0,
                "last_notification": None,
                "metadata": alert_data.get("metadata", {}),
            }

            # Store alert
            self.active_alerts[alert_id] = alert
            self.alert_history.append(alert.copy())

            # Check if immediate notification is needed
            if level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
                await self._send_notification(alert, "immediate")

        except Exception as e:
            self.logger.error(f"Error creating alert: {str(e)}")

    async def _check_alert_states(self):
        """检查告警状态"""
        try:
            current_time = datetime.now()

            for alert_id, alert in list(self.active_alerts.items()):
                # 检查是否已经解决
                if await self._check_alert_resolved(alert):
                    alert["state"] = AlertState.RESOLVED
                    alert["resolved_at"] = current_time

                    # 更新指标
                    self.metrics.active_alerts.labels(level=alert["level"].value).dec()
                    self.metrics.recovery_count.inc()

                    # 记录持续时间
                    duration = (current_time - alert["timestamp"]).total_seconds()
                    self.metrics.alert_duration.observe(duration)

                    # 移除活动告警
                    del self.active_alerts[alert_id]

                # 检查是否需要自动解决
                elif (
                    current_time - alert["timestamp"]
                ).total_seconds() > self.alert_config["auto_resolve_timeout"]:
                    await self._auto_resolve_alert(alert)

        except Exception as e:
            self.logger.error(f"Error checking alert states: {str(e)}")

    async def _check_alert_resolved(self, alert: Dict) -> bool:
        """Check if alert is resolved with enhanced category handling"""
        try:
            # Check recovery count
            if alert["recovery_count"] >= self.alert_config["recovery_threshold"]:
                return True

            # Check alert category
            category = alert.get("category", AlertCategory.SYSTEM)
            
            if category == AlertCategory.SYSTEM:
                return await self._check_system_recovery(alert)
            elif category == AlertCategory.DEX:
                return await self._check_dex_recovery(alert)
            elif category == AlertCategory.MEME:
                return await self._check_meme_recovery(alert)
            elif category == AlertCategory.CROSS_DEX:
                return await self._check_cross_dex_recovery(alert)
            else:
                return await self._check_application_recovery(alert)

        except Exception as e:
            self.logger.error(f"Error checking alert resolution: {str(e)}")
            return False

    async def _check_dex_recovery(self, alert: Dict) -> bool:
        """Check DEX alert recovery"""
        try:
            metrics = alert.get("metadata", {})
            alert_type = metrics.get("type")

            if alert_type == "liquidity":
                current = float(metrics.get("current_liquidity", 0))
                threshold = float(metrics.get("threshold", 0))
                return current >= threshold
            elif alert_type == "slippage":
                current = float(metrics.get("current_slippage", 0))
                threshold = float(metrics.get("threshold", 0))
                return current <= threshold
            return False
        except Exception as e:
            self.logger.error(f"Error checking DEX recovery: {str(e)}")
            return False

    async def _check_meme_recovery(self, alert: Dict) -> bool:
        """Check meme token alert recovery"""
        try:
            metrics = alert.get("metadata", {})
            alert_type = metrics.get("type")

            if alert_type == "volume":
                current = float(metrics.get("current_volume", 0))
                threshold = float(metrics.get("threshold", 0))
                return current >= threshold
            elif alert_type == "holders":
                current = int(metrics.get("current_holders", 0))
                threshold = int(metrics.get("threshold", 0))
                return current >= threshold
            return False
        except Exception as e:
            self.logger.error(f"Error checking meme recovery: {str(e)}")
            return False

    async def _check_cross_dex_recovery(self, alert: Dict) -> bool:
        """Check cross-DEX alert recovery"""
        try:
            metrics = alert.get("metadata", {})
            alert_type = metrics.get("type")

            if alert_type == "spread":
                current = float(metrics.get("current_spread", 0))
                threshold = float(metrics.get("threshold", 0))
                return current <= threshold
            elif alert_type == "arbitrage":
                current = float(metrics.get("current_opportunity", 0))
                threshold = float(metrics.get("threshold", 0))
                return current <= threshold
            return False
        except Exception as e:
            self.logger.error(f"Error checking cross-DEX recovery: {str(e)}")
            return False

    async def _aggregate_alerts(self):
        """Aggregate alerts with enhanced categorization"""
        try:
            # Group by category and level
            groups = {}
            for alert in self.active_alerts.values():
                category = alert.get("category", AlertCategory.SYSTEM)
                key = (category, alert["level"])
                if key not in groups:
                    groups[key] = []
                groups[key].append(alert)

            # Process each group
            for (category, level), alerts in groups.items():
                if len(alerts) > 1:
                    # Special handling for different categories
                    if category == AlertCategory.MEME:
                        await self._aggregate_meme_alerts(alerts)
                    elif category == AlertCategory.DEX:
                        await self._aggregate_dex_alerts(alerts)
                    elif category == AlertCategory.CROSS_DEX:
                        await self._aggregate_cross_dex_alerts(alerts)
                    else:
                        # Default aggregation for other categories
                        aggregated = {
                            "id": f"agg_{category.value}_{level.value}_{datetime.now().strftime('%Y%m%d%H%M')}",
                            "level": level,
                            "category": category,
                            "message": f"Multiple {category.value} alerts ({len(alerts)} alerts)",
                            "timestamp": datetime.now(),
                            "state": AlertState.ACTIVE,
                            "aggregated": True,
                            "alerts": alerts,
                            "metadata": self._merge_alert_metadata(alerts)
                        }

                        # Replace original alerts
                        for alert in alerts:
                            if alert["id"] in self.active_alerts:
                                del self.active_alerts[alert["id"]]

                        self.active_alerts[aggregated["id"]] = aggregated

        except Exception as e:
            self.logger.error(f"Error aggregating alerts: {str(e)}")

    async def _aggregate_meme_alerts(self, alerts: List[Dict]):
        """Aggregate meme token specific alerts"""
        try:
            tokens = {}
            for alert in alerts:
                token = alert["metadata"].get("token", "unknown")
                if token not in tokens:
                    tokens[token] = []
                tokens[token].append(alert)

            for token, token_alerts in tokens.items():
                # Calculate risk metrics
                risk_score = self._calculate_meme_risk_score(token_alerts)
                volume_change = np.mean([float(a["metadata"].get("volume_change", 0)) for a in token_alerts])
                sentiment_change = np.mean([float(a["metadata"].get("sentiment_change", 0)) for a in token_alerts])

                aggregated = {
                    "id": f"meme_{token}_{datetime.now().strftime('%Y%m%d%H%M')}",
                    "level": self._determine_meme_alert_level(risk_score),
                    "category": AlertCategory.MEME,
                    "message": f"Meme token {token} risk score: {risk_score:.2f}, Volume change: {volume_change:.1f}%, Sentiment: {sentiment_change:.1f}",
                    "timestamp": datetime.now(),
                    "state": AlertState.ACTIVE,
                    "aggregated": True,
                    "alerts": token_alerts,
                    "metadata": {
                        "token": token,
                        "risk_score": risk_score,
                        "volume_change": volume_change,
                        "sentiment_change": sentiment_change
                    }
                }

                # Replace original alerts
                for alert in token_alerts:
                    if alert["id"] in self.active_alerts:
                        del self.active_alerts[alert["id"]]

                self.active_alerts[aggregated["id"]] = aggregated

        except Exception as e:
            self.logger.error(f"Error aggregating meme alerts: {str(e)}")

    async def _aggregate_dex_alerts(self, alerts: List[Dict]):
        """Aggregate DEX specific alerts"""
        try:
            dexes = {}
            for alert in alerts:
                dex = alert["metadata"].get("dex", "unknown")
                if dex not in dexes:
                    dexes[dex] = []
                dexes[dex].append(alert)

            for dex, dex_alerts in dexes.items():
                # Calculate DEX metrics
                liquidity_score = float(np.mean([float(a["metadata"].get("liquidity_ratio", 0)) for a in dex_alerts]))
                execution_score = float(np.mean([float(a["metadata"].get("execution_time", 0)) / 5.0 for a in dex_alerts]))
                reliability_score = float(np.mean([float(a["metadata"].get("success_rate", 0)) for a in dex_alerts]))

                aggregated = {
                    "id": f"dex_{dex}_{datetime.now().strftime('%Y%m%d%H%M')}",
                    "level": self._determine_dex_alert_level(liquidity_score, execution_score, reliability_score),
                    "category": AlertCategory.DEX,
                    "message": f"DEX {dex} metrics - Liquidity: {liquidity_score:.2f}, Execution: {execution_score:.2f}, Reliability: {reliability_score:.2f}",
                    "timestamp": datetime.now(),
                    "state": AlertState.ACTIVE,
                    "aggregated": True,
                    "alerts": dex_alerts,
                    "metadata": {
                        "dex": dex,
                        "liquidity_score": liquidity_score,
                        "execution_score": execution_score,
                        "reliability_score": reliability_score
                    }
                }

                # Replace original alerts
                for alert in dex_alerts:
                    if alert["id"] in self.active_alerts:
                        del self.active_alerts[alert["id"]]

                self.active_alerts[aggregated["id"]] = aggregated

        except Exception as e:
            self.logger.error(f"Error aggregating DEX alerts: {str(e)}")

    async def _aggregate_cross_dex_alerts(self, alerts: List[Dict]):
        """Aggregate cross-DEX alerts"""
        try:
            pairs = {}
            for alert in alerts:
                pair = alert["metadata"].get("token_pair", "unknown")
                if pair not in pairs:
                    pairs[pair] = []
                pairs[pair].append(alert)

            for pair, pair_alerts in pairs.items():
                # Calculate cross-DEX metrics
                spread_score = float(np.mean([float(a["metadata"].get("spread_bps", 0)) / 100 for a in pair_alerts]))
                arbitrage_score = float(np.mean([float(a["metadata"].get("arbitrage_opportunity", 0)) for a in pair_alerts]))
                risk_score = float(self._calculate_cross_dex_risk_score(pair_alerts))

                aggregated = {
                    "id": f"cross_dex_{pair}_{datetime.now().strftime('%Y%m%d%H%M')}",
                    "level": self._determine_cross_dex_alert_level(spread_score, arbitrage_score, risk_score),
                    "category": AlertCategory.CROSS_DEX,
                    "message": f"Cross-DEX {pair} - Spread: {spread_score:.2f}%, Arbitrage: {arbitrage_score:.2f}, Risk: {risk_score:.2f}",
                    "timestamp": datetime.now(),
                    "state": AlertState.ACTIVE,
                    "aggregated": True,
                    "alerts": pair_alerts,
                    "metadata": {
                        "token_pair": pair,
                        "spread_score": spread_score,
                        "arbitrage_score": arbitrage_score,
                        "risk_score": risk_score
                    }
                }

                # Replace original alerts
                for alert in pair_alerts:
                    if alert["id"] in self.active_alerts:
                        del self.active_alerts[alert["id"]]

                self.active_alerts[aggregated["id"]] = aggregated

        except Exception as e:
            self.logger.error(f"Error aggregating cross-DEX alerts: {str(e)}")

    def _merge_alert_metadata(self, alerts: List[Dict]) -> Dict:
        """Merge metadata from multiple alerts"""
        try:
            merged = {}
            for alert in alerts:
                for key, value in alert.get("metadata", {}).items():
                    if key not in merged:
                        merged[key] = []
                    if value not in merged[key]:
                        merged[key].append(value)
            return merged
        except Exception as e:
            self.logger.error(f"Error merging alert metadata: {str(e)}")
            return {}

    async def _send_notifications(self):
        """发送通知"""
        try:
            current_time = datetime.now()

            # 检查每个活动告警
            for alert in self.active_alerts.values():
                # 检查是否需要发送通知
                if self._should_send_notification(alert, current_time):
                    # 获取通知渠道
                    channels = self._get_notification_channels(alert)

                    # 发送通知
                    for channel in channels:
                        try:
                            await self._send_notification(alert, channel)
                            self.metrics.notification_count.labels(
                                channel=channel
                            ).inc()
                        except Exception as e:
                            self.logger.error(
                                f"Error sending notification via {channel}: {str(e)}"
                            )

                    # 更新最后通知时间
                    alert["last_notification"] = current_time

        except Exception as e:
            self.logger.error(f"Error sending notifications: {str(e)}")

    def _should_send_notification(self, alert: Dict, current_time: datetime) -> bool:
        """检查是否应该发送通知"""
        # 检查是否是首次通知
        if alert["last_notification"] is None:
            return True

        # 检查冷却时间
        cooldown = self.alert_config["notification_cooldown"]
        if (current_time - alert["last_notification"]).total_seconds() < cooldown:
            return False

        # 检查通知次数限制
        notification_key = f"{alert['source']}_{current_time.strftime('%Y%m%d%H')}"
        if (
            self.notification_history.get(notification_key, 0)
            >= self.alert_config["max_notifications"]
        ):
            return False

        return True

    def _get_notification_channels(self, alert: Dict) -> List[str]:
        """获取通知渠道"""
        channels = []

        # 根据告警级别选择渠道
        if alert["level"] == AlertLevel.CRITICAL:
            channels.extend(["email", "sms", "slack"])
        elif alert["level"] == AlertLevel.ERROR:
            channels.extend(["email", "slack"])
        elif alert["level"] == AlertLevel.WARNING:
            channels.append("slack")
        else:
            channels.append("slack")

        return channels

    async def _send_notification(self, alert: Dict, channel: str):
        """发送通知"""
        try:
            if channel == "email":
                await self._send_email_notification(alert)
            elif channel == "slack":
                await self._send_slack_notification(alert)
            elif channel == "sms":
                await self._send_sms_notification(alert)
            elif channel == "immediate":
                await self._send_immediate_notification(alert)

        except Exception as e:
            self.logger.error(f"Error sending {channel} notification: {str(e)}")

    async def _send_immediate_notification(self, alert: Dict):
        """Send immediate notification for critical alerts"""
        try:
            channels = ["email", "sms", "slack"]
            for channel in channels:
                await self._send_notification(alert, channel)
        except Exception as e:
            self.logger.error(f"Error sending immediate notification: {str(e)}")

    async def _send_email_notification(self, alert: Dict):
        """发送邮件通知"""
        try:
            # 获取邮件配置
            smtp_config = self.config.get("smtp_config", {})
            if not smtp_config:
                self.logger.error("SMTP configuration missing")
                return

            # 创建邮件内容
            msg = MIMEMultipart()
            msg["From"] = smtp_config.get("from_email")
            msg["To"] = smtp_config.get("to_email")
            msg[
                "Subject"
            ] = f"[{alert['level'].value.upper()}] Alert from {alert['source']}"

            # 构建邮件正文
            body = f"""
            Alert Details:
            --------------
            Level: {alert['level'].value.upper()}
            Source: {alert['source']}
            Message: {alert['message']}
            Time: {alert['timestamp'].isoformat()}
            
            Additional Information:
            ----------------------
            Alert ID: {alert['id']}
            Check Count: {alert['check_count']}
            Recovery Count: {alert['recovery_count']}
            
            Metadata:
            ---------
            {json.dumps(alert['metadata'], indent=2)}
            """

            msg.attach(MIMEText(body, "plain"))

            # 发送邮件
            await aiosmtplib.send(
                msg,
                hostname=smtp_config.get("host"),
                port=smtp_config.get("port"),
                username=smtp_config.get("username"),
                password=smtp_config.get("password"),
                use_tls=smtp_config.get("use_tls", True),
            )

        except Exception as e:
            raise Exception(f"Email notification error: {str(e)}")

    async def _send_slack_notification(self, alert: Dict):
        """发送Slack通知"""
        try:
            webhook_url = self.config.get("slack_webhook_url")
            if not webhook_url:
                return

            # 构建消息
            message = {
                "text": f"*{alert['level'].value.upper()} Alert*\n"
                f"*Message:* {alert['message']}\n"
                f"*Source:* {alert['source']}\n"
                f"*Time:* {alert['timestamp'].isoformat()}"
            }

            # 发送消息
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=message) as response:
                    if response.status >= 400:
                        raise Exception(f"Slack API error: {response.status}")

        except Exception as e:
            raise Exception(f"Slack notification error: {str(e)}")

    async def _send_sms_notification(self, alert: Dict):
        """发送短信通知"""
        try:
            # 获取短信配置
            sms_config = self.config.get("sms_config", {})
            if not sms_config:
                self.logger.error("SMS configuration missing")
                return

            # 构建短信内容
            message = (
                f"[{alert['level'].value.upper()}] "
                f"{alert['source']}: {alert['message']} "
                f"Time: {alert['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"
            )

            # 根据不同的短信服务商选择不同的实现
            provider = sms_config.get("provider", "twilio")

            if provider == "twilio":
                await self._send_twilio_sms(message, sms_config)
            elif provider == "aws_sns":
                await self._send_aws_sns(message, sms_config)
            elif provider == "aliyun":
                await self._send_aliyun_sms(message, sms_config)
            else:
                raise ValueError(f"Unsupported SMS provider: {provider}")

        except Exception as e:
            raise Exception(f"SMS notification error: {str(e)}")

    async def _send_twilio_sms(self, message: str, config: Dict):
        """通过Twilio发送短信"""
        try:
            from twilio.rest import Client

            # 创建Twilio客户端
            client = Client(config["account_sid"], config["auth_token"])

            # 发送短信
            message = await asyncio.to_thread(
                client.messages.create,
                body=message,
                from_=config["from_number"],
                to=config["to_number"],
            )

        except Exception as e:
            raise Exception(f"Twilio SMS error: {str(e)}")

    async def _send_aws_sns(self, message: str, config: Dict):
        """通过AWS SNS发送短信"""
        try:
            import boto3

            # 创建SNS客户端
            sns = boto3.client(
                "sns",
                aws_access_key_id=config["aws_access_key_id"],
                aws_secret_access_key=config["aws_secret_access_key"],
                region_name=config["region_name"],
            )

            # 发送短信
            await asyncio.to_thread(
                sns.publish, PhoneNumber=config["to_number"], Message=message
            )

        except Exception as e:
            raise Exception(f"AWS SNS error: {str(e)}")

    async def _send_aliyun_sms(self, message: str, config: Dict):
        """通过阿里云发送短信"""
        try:
            from aliyunsdkcore.client import AcsClient
            from aliyunsdkcore.request import CommonRequest

            # 创建ACS客户端
            client = AcsClient(
                config["access_key_id"],
                config["access_key_secret"],
                config["region_id"],
            )

            # 创建请求
            request = CommonRequest()
            request.set_accept_format("json")
            request.set_domain("dysmsapi.aliyuncs.com")
            request.set_method("POST")
            request.set_version("2017-05-25")
            request.set_action_name("SendSms")
            request.add_query_param("PhoneNumbers", config["to_number"])
            request.add_query_param("SignName", config["sign_name"])
            request.add_query_param("TemplateCode", config["template_code"])
            request.add_query_param("TemplateParam", message)

            # 发送短信
            await asyncio.to_thread(client.do_action_with_exception, request)

        except Exception as e:
            raise Exception(f"Aliyun SMS error: {str(e)}")

    async def _check_auto_recovery(self):
        """检查自动恢复"""
        try:
            for alert in list(self.active_alerts.values()):
                # 增加检查计数
                alert["check_count"] += 1

                # 检查是否恢复
                if await self._check_recovery_condition(alert):
                    alert["recovery_count"] += 1
                else:
                    alert["recovery_count"] = 0

        except Exception as e:
            self.logger.error(f"Error checking auto recovery: {str(e)}")

    async def _check_recovery_condition(self, alert: Dict) -> bool:
        """检查恢复条件"""
        try:
            # 根据告警类型检查不同的恢复条件
            if alert["source"] == "system":
                return await self._check_system_recovery(alert)
            elif alert["source"] == "application":
                return await self._check_application_recovery(alert)
            else:
                return False

        except Exception as e:
            self.logger.error(f"Error checking recovery condition: {str(e)}")
            return False

    async def _check_system_recovery(self, alert: Dict) -> bool:
        """检查系统恢复"""
        try:
            # 获取系统指标
            metrics = {}

            # CPU使用率检查
            if alert["metadata"].get("type") == "cpu_usage":
                cpu_percent = psutil.cpu_percent(interval=1)
                metrics["cpu_usage"] = cpu_percent
                return cpu_percent < alert["metadata"].get("threshold", 80)

            # 内存使用率检查
            elif alert["metadata"].get("type") == "memory_usage":
                memory = psutil.virtual_memory()
                metrics["memory_usage"] = memory.percent
                return memory.percent < alert["metadata"].get("threshold", 80)

            # 磁盘使用率检查
            elif alert["metadata"].get("type") == "disk_usage":
                disk = psutil.disk_usage("/")
                metrics["disk_usage"] = disk.percent
                return disk.percent < alert["metadata"].get("threshold", 80)

            # 网络连接检查
            elif alert["metadata"].get("type") == "network":
                try:
                    host = alert["metadata"].get("host", "8.8.8.8")
                    delay = await aioping.ping(host)
                    metrics["network_latency"] = delay
                    return delay < alert["metadata"].get("threshold", 1.0)
                except:
                    return False

            # 进程检查
            elif alert["metadata"].get("type") == "process":
                process_name = alert["metadata"].get("process_name")
                if not process_name:
                    return False

                for proc in psutil.process_iter(["name"]):
                    if proc.info["name"] == process_name:
                        return True
                return False

            # 默认不恢复
            return False

        except Exception as e:
            self.logger.error(f"System recovery check error: {str(e)}")
            return False

    async def _check_application_recovery(self, alert: Dict) -> bool:
        """检查应用恢复"""
        try:
            # 获取应用指标
            metrics = {}

            # API健康检查
            if alert["metadata"].get("type") == "api_health":
                try:
                    url = alert["metadata"].get("url")
                    if not url:
                        return False

                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=5) as response:
                            metrics["api_status"] = response.status
                            return response.status < 400
                except:
                    return False

            # 数据库连接检查
            elif alert["metadata"].get("type") == "database":
                try:
                    db_url = alert["metadata"].get("db_url")
                    if not db_url:
                        return False

                    conn = await asyncpg.connect(db_url)
                    try:
                        await conn.fetch("SELECT 1")
                        return True
                    finally:
                        await conn.close()
                except:
                    return False

            # 队列积压检查
            elif alert["metadata"].get("type") == "queue_backlog":
                queue_size = alert["metadata"].get("current_size", 0)
                threshold = alert["metadata"].get("threshold", 1000)
                metrics["queue_size"] = queue_size
                return queue_size < threshold

            # 错误率检查
            elif alert["metadata"].get("type") == "error_rate":
                error_rate = alert["metadata"].get("current_rate", 0)
                threshold = alert["metadata"].get("threshold", 0.05)
                metrics["error_rate"] = error_rate
                return error_rate < threshold

            # 响应时间检查
            elif alert["metadata"].get("type") == "response_time":
                response_time = alert["metadata"].get("current_time", 0)
                threshold = alert["metadata"].get("threshold", 1.0)
                metrics["response_time"] = response_time
                return response_time < threshold

            # 默认不恢复
            return False

        except Exception as e:
            self.logger.error(f"Application recovery check error: {str(e)}")
            return False

    def _cleanup_history(self):
        """清理历史数据"""
        try:
            current_time = datetime.now()

            # 清理告警历史
            cutoff_time = current_time - timedelta(days=7)
            self.alert_history = [
                alert
                for alert in self.alert_history
                if alert["timestamp"] > cutoff_time
            ]

            # 清理通知历史
            for key in list(self.notification_history.keys()):
                if key.endswith(current_time.strftime("%Y%m%d%H")):
                    continue
                del self.notification_history[key]

        except Exception as e:
            self.logger.error(f"Error cleaning up history: {str(e)}")

    def get_alert_stats(self) -> Dict:
        """获取告警统计"""
        return {
            "active_alerts": len(self.active_alerts),
            "alert_history": len(self.alert_history),
            "alerts_by_level": {
                level.value: sum(
                    1 for a in self.active_alerts.values() if a["level"] == level
                )
                for level in AlertLevel
            },
            "alerts_by_source": {
                source: len(list(alerts))
                for source, alerts in itertools.groupby(
                    sorted(self.active_alerts.values(), key=lambda x: x["source"]),
                    key=lambda x: x["source"],
                )
            },
        }

    async def _auto_resolve_alert(self, alert: Dict):
        """自动解决告警"""
        try:
            # 检查是否需要自动解决
            if await self._check_auto_recovery():
                alert["state"] = AlertState.RESOLVED
                alert["resolved_at"] = datetime.now()

                # 更新指标
                self.metrics.active_alerts.labels(level=alert["level"].value).dec()
                self.metrics.recovery_count.inc()

                # 记录持续时间
                duration = (datetime.now() - alert["timestamp"]).total_seconds()
                self.metrics.alert_duration.observe(duration)

                # 移除活动告警
                del self.active_alerts[alert["id"]]

                # 立即发送通知
                await self._send_immediate_notification(alert)

        except Exception as e:
            self.logger.error(f"Error auto-resolving alert: {str(e)}")

    async def _escalate_alert(self, alert: Dict):
        """告警升级"""
        try:
            # 检查是否需要升级
            if not self._should_escalate_alert(alert):
                return

            # 更新告警级别
            old_level = alert["level"]
            new_level = self._get_escalated_level(old_level)

            if new_level != old_level:
                alert["level"] = new_level
                alert["escalated_at"] = datetime.now()
                alert["escalation_count"] = alert.get("escalation_count", 0) + 1

                # 更新指标
                self.metrics.active_alerts.labels(level=old_level.value).dec()
                self.metrics.active_alerts.labels(level=new_level.value).inc()

                # 记录升级事件
                self._record_escalation_event(alert, old_level, new_level)

                # 立即发送通知
                await self._send_immediate_notification(alert)

        except Exception as e:
            self.logger.error(f"Alert escalation error: {str(e)}")

    def _should_escalate_alert(self, alert: Dict) -> bool:
        """检查是否应该升级告警"""
        try:
            # 检查是否已经是最高级别
            if alert["level"] == AlertLevel.CRITICAL:
                return False

            # 检查是否超过升级阈值
            current_time = datetime.now()
            alert_age = (current_time - alert["timestamp"]).total_seconds()

            # 根据不同级别设置不同的升级阈值
            thresholds = {
                AlertLevel.INFO: 3600,  # 1小时
                AlertLevel.WARNING: 1800,  # 30分钟
                AlertLevel.ERROR: 900,  # 15分钟
            }

            return alert_age > thresholds.get(alert["level"], 3600)

        except Exception as e:
            self.logger.error(f"Error checking alert escalation: {str(e)}")
            return False

    def _get_escalated_level(self, current_level: AlertLevel) -> AlertLevel:
        """获取升级后的告警级别"""
        escalation_map = {
            AlertLevel.INFO: AlertLevel.WARNING,
            AlertLevel.WARNING: AlertLevel.ERROR,
            AlertLevel.ERROR: AlertLevel.CRITICAL,
            AlertLevel.CRITICAL: AlertLevel.CRITICAL,
        }
        return escalation_map.get(current_level, current_level)

    def _record_escalation_event(
        self, alert: Dict, old_level: AlertLevel, new_level: AlertLevel
    ):
        """记录升级事件"""
        event = {
            "alert_id": alert["id"],
            "timestamp": datetime.now(),
            "old_level": old_level.value,
            "new_level": new_level.value,
            "reason": "timeout",
            "escalation_count": alert.get("escalation_count", 1),
        }

        if not hasattr(self, "escalation_history"):
            self.escalation_history = []
        self.escalation_history.append(event)

    def get_alert_analysis(self) -> Dict:
        """获取告警分析"""
        try:
            current_time = datetime.now()
            analysis_window = timedelta(days=7)
            start_time = current_time - analysis_window

            # 过滤分析窗口内的告警
            alerts = [
                alert for alert in self.alert_history if alert["timestamp"] > start_time
            ]

            # 计算统计指标
            total_alerts = len(alerts)
            if total_alerts == 0:
                return self._get_empty_analysis()

            analysis = {
                "total_alerts": total_alerts,
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": current_time.isoformat(),
                },
                "alerts_by_level": self._get_alerts_by_level(alerts),
                "alerts_by_source": self._get_alerts_by_source(alerts),
                "resolution_stats": self._get_resolution_stats(alerts),
                "escalation_stats": self._get_escalation_stats(),
                "peak_times": self._get_peak_alert_times(alerts),
                "trends": self._get_alert_trends(alerts),
                "common_patterns": self._get_common_patterns(alerts),
            }

            return analysis

        except Exception as e:
            self.logger.error(f"Error generating alert analysis: {str(e)}")
            return self._get_empty_analysis()

    def _get_empty_analysis(self) -> Dict:
        """获取空分析结果"""
        return {
            "total_alerts": 0,
            "time_range": {
                "start": datetime.now().isoformat(),
                "end": datetime.now().isoformat(),
            },
            "alerts_by_level": {},
            "alerts_by_source": {},
            "resolution_stats": {"avg_resolution_time": 0, "resolution_rate": 0},
            "escalation_stats": {"total_escalations": 0, "avg_escalation_time": 0},
            "peak_times": [],
            "trends": {},
            "common_patterns": [],
        }

    def _get_alerts_by_level(self, alerts: List[Dict]) -> Dict:
        """按级别统计告警"""
        stats = {}
        for level in AlertLevel:
            count = sum(1 for a in alerts if a["level"] == level)
            stats[level.value] = {
                "count": count,
                "percentage": count / len(alerts) * 100 if alerts else 0,
            }
        return stats

    def _get_alerts_by_source(self, alerts: List[Dict]) -> Dict:
        """按来源统计告警"""
        stats = {}
        for alert in alerts:
            source = alert["source"]
            if source not in stats:
                stats[source] = {
                    "count": 0,
                    "by_level": {level.value: 0 for level in AlertLevel},
                }
            stats[source]["count"] += 1
            stats[source]["by_level"][alert["level"].value] += 1
        return stats

    def _get_resolution_stats(self, alerts: List[Dict]) -> Dict:
        """获取解决统计"""
        resolved_alerts = [a for a in alerts if a.get("resolved_at")]
        if not resolved_alerts:
            return {"avg_resolution_time": 0, "resolution_rate": 0}

        resolution_times = [
            (a["resolved_at"] - a["timestamp"]).total_seconds() for a in resolved_alerts
        ]

        return {
            "avg_resolution_time": sum(resolution_times) / len(resolution_times),
            "resolution_rate": len(resolved_alerts) / len(alerts) * 100,
        }

    def _get_escalation_stats(self) -> Dict:
        """获取升级统计"""
        if not hasattr(self, "escalation_history"):
            return {"total_escalations": 0, "avg_escalation_time": 0}

        return {
            "total_escalations": len(self.escalation_history),
            "avg_escalation_time": self._calculate_avg_escalation_time(),
        }

    def _get_peak_alert_times(self, alerts: List[Dict]) -> List[Dict]:
        """获取告警高峰时间"""
        # 按小时统计
        hour_counts = {}
        for alert in alerts:
            hour = alert["timestamp"].hour
            hour_counts[hour] = hour_counts.get(hour, 0) + 1

        # 找出前3个高峰时间
        peak_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]

        return [{"hour": hour, "count": count} for hour, count in peak_hours]

    def _get_alert_trends(self, alerts: List[Dict]) -> Dict:
        """获取告警趋势"""
        # 按天统计
        daily_counts = {}
        for alert in alerts:
            day = alert["timestamp"].date()
            if day not in daily_counts:
                daily_counts[day] = {
                    "total": 0,
                    "by_level": {level.value: 0 for level in AlertLevel},
                }
            daily_counts[day]["total"] += 1
            daily_counts[day]["by_level"][alert["level"].value] += 1

        # 计算趋势
        days = sorted(daily_counts.keys())
        if len(days) < 2:
            return {"trend": "stable", "change_rate": 0}

        first_day = days[0]
        last_day = days[-1]
        change_rate = (
            (daily_counts[last_day]["total"] - daily_counts[first_day]["total"])
            / daily_counts[first_day]["total"]
            * 100
        )

        trend = (
            "increasing"
            if change_rate > 10
            else "decreasing"
            if change_rate < -10
            else "stable"
        )

        return {
            "trend": trend,
            "change_rate": change_rate,
            "daily_counts": daily_counts,
        }

    def _get_common_patterns(self, alerts: List[Dict]) -> List[Dict]:
        """获取常见告警模式"""
        # 统计消息模式
        patterns = {}
        for alert in alerts:
            message = alert["message"]
            if message not in patterns:
                patterns[message] = {"count": 0, "sources": set(), "levels": set()}
            patterns[message]["count"] += 1
            patterns[message]["sources"].add(alert["source"])
            patterns[message]["levels"].add(alert["level"].value)

        # 找出前5个最常见的模式
        common_patterns = sorted(
            patterns.items(), key=lambda x: x[1]["count"], reverse=True
        )[:5]

        return [
            {
                "message": message,
                "count": stats["count"],
                "sources": list(stats["sources"]),
                "levels": list(stats["levels"]),
            }
            for message, stats in common_patterns
        ]

    def _calculate_avg_escalation_time(self) -> float:
        """Calculate average escalation time"""
        if not self.escalation_history:
            return 0

        total_time = sum(
            (
                event["timestamp"]
                - datetime.fromisoformat(event["timestamp"].isoformat())
            ).total_seconds()
            for event in self.escalation_history
        )

        return total_time / len(self.escalation_history)

    def _calculate_meme_risk_score(self, alerts: List[Dict]) -> float:
        """Calculate risk score for meme token alerts"""
        if not alerts:
            return 0.0

        weights = {
            "volume": 0.3,
            "holders": 0.2,
            "sentiment": 0.3,
            "virality": 0.2
        }

        scores = []
        for alert in alerts:
            metrics = alert.get("metadata", {})
            score = 0.0
            
            if "volume_change" in metrics:
                score += weights["volume"] * min(abs(float(metrics["volume_change"])) / 100, 1.0)
            if "holders_change" in metrics:
                score += weights["holders"] * min(abs(float(metrics["holders_change"])) / 50, 1.0)
            if "sentiment_score" in metrics:
                score += weights["sentiment"] * (1 - float(metrics["sentiment_score"]))
            if "viral_coefficient" in metrics:
                score += weights["virality"] * min(float(metrics["viral_coefficient"]) / 2, 1.0)
            
            scores.append(score)

        return float(np.mean(scores))

    def _calculate_dex_risk_score(self, alerts: List[Dict]) -> float:
        """Calculate risk score for DEX alerts"""
        if not alerts:
            return 0.0

        weights = {
            "liquidity": 0.4,
            "slippage": 0.3,
            "execution": 0.3
        }

        scores = []
        for alert in alerts:
            metrics = alert.get("metadata", {})
            score = 0.0
            
            if "liquidity_ratio" in metrics:
                score += weights["liquidity"] * (1 - float(metrics["liquidity_ratio"]))
            if "slippage" in metrics:
                score += weights["slippage"] * min(float(metrics["slippage"]) / 0.05, 1.0)
            if "execution_time" in metrics:
                score += weights["execution"] * min(float(metrics["execution_time"]) / 5.0, 1.0)
            
            scores.append(score)

        return float(np.mean(scores))

    def _calculate_cross_dex_risk_score(self, alerts: List[Dict]) -> float:
        """Calculate risk score for cross-DEX alerts"""
        if not alerts:
            return 0.0

        weights = {
            "spread": 0.5,
            "liquidity_imbalance": 0.3,
            "execution_risk": 0.2
        }

        scores = []
        for alert in alerts:
            metrics = alert.get("metadata", {})
            score = 0.0
            
            if "spread_bps" in metrics:
                score += weights["spread"] * min(float(metrics["spread_bps"]) / 100, 1.0)
            if "liquidity_imbalance" in metrics:
                score += weights["liquidity_imbalance"] * min(float(metrics["liquidity_imbalance"]), 1.0)
            if "execution_risk" in metrics:
                score += weights["execution_risk"] * float(metrics["execution_risk"])
            
            scores.append(score)

        return float(np.mean(scores))

    def _determine_meme_alert_level(self, risk_score: float) -> AlertLevel:
        """Determine alert level based on meme token risk score"""
        if risk_score >= 0.8:
            return AlertLevel.CRITICAL
        elif risk_score >= 0.6:
            return AlertLevel.ERROR
        elif risk_score >= 0.4:
            return AlertLevel.WARNING
        return AlertLevel.INFO

    def _determine_dex_alert_level(
        self, liquidity_score: float, execution_score: float, reliability_score: float
    ) -> AlertLevel:
        """Determine alert level based on DEX metrics"""
        risk_score = (
            liquidity_score * 0.4 + 
            execution_score * 0.3 + 
            reliability_score * 0.3
        )
        
        if risk_score >= 0.8:
            return AlertLevel.CRITICAL
        elif risk_score >= 0.6:
            return AlertLevel.ERROR
        elif risk_score >= 0.4:
            return AlertLevel.WARNING
        return AlertLevel.INFO

    def _determine_cross_dex_alert_level(
        self, spread_score: float, arbitrage_score: float, risk_score: float
    ) -> AlertLevel:
        """Determine alert level based on cross-DEX metrics"""
        total_score = (
            spread_score * 0.4 + 
            arbitrage_score * 0.3 + 
            risk_score * 0.3
        )
        
        if total_score >= 0.8:
            return AlertLevel.CRITICAL
        elif total_score >= 0.6:
            return AlertLevel.ERROR
        elif total_score >= 0.4:
            return AlertLevel.WARNING
        return AlertLevel.INFO

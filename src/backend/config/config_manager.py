import asyncio
import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

import yaml
from prometheus_client import Counter, Gauge
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class ConfigSource(Enum):
    FILE = "file"
    ENV = "env"
    REMOTE = "remote"


class ConfigPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ConfigMetrics:
    """配置指标"""

    update_count: Counter
    config_errors: Counter
    last_update_time: Gauge
    active_configs: Gauge


class ConfigManager:
    def __init__(self, base_config: Dict):
        self.base_config = base_config
        self.config_cache = {}
        self.watchers = {}
        self.handlers = {}
        self.remote_configs = {}

        # 配置指标
        self.metrics = ConfigMetrics(
            update_count=Counter(
                "config_updates_total", "Total number of config updates"
            ),
            config_errors=Counter(
                "config_errors_total", "Total number of config errors"
            ),
            last_update_time=Gauge(
                "config_last_update_time", "Last config update timestamp"
            ),
            active_configs=Gauge("active_configs", "Number of active configurations"),
        )

        # 初始化配置
        self._init_config()

        # 启动文件监控
        self._start_file_watchers()

    def _init_config(self):
        """初始化配置"""
        try:
            # 加载基础配置
            self.config = self.base_config.copy()

            # 加载环境变量
            self._load_env_vars()

            # 加载配置文件
            self._load_config_files()

            # 加载远程配置
            self._load_remote_configs()

            # 更新指标
            self.metrics.active_configs.set(len(self.config))
            self.metrics.last_update_time.set_to_current_time()

        except Exception as e:
            self.logger.error(f"Error initializing config: {str(e)}")
            self.metrics.config_errors.inc()

    def _load_env_vars(self):
        """加载环境变量"""
        try:
            env_prefix = self.base_config.get("env_prefix", "APP_")

            for key, value in os.environ.items():
                if key.startswith(env_prefix):
                    config_key = key[len(env_prefix) :].lower()
                    # 尝试解析JSON值
                    try:
                        self.config[config_key] = json.loads(value)
                    except:
                        self.config[config_key] = value

        except Exception as e:
            self.logger.error(f"Error loading environment variables: {str(e)}")
            self.metrics.config_errors.inc()

    def _load_config_files(self):
        """加载配置文件"""
        try:
            config_files = self.base_config.get("config_files", [])

            for file_config in config_files:
                path = file_config["path"]
                priority = ConfigPriority(file_config.get("priority", "MEDIUM"))

                if os.path.exists(path):
                    with open(path, "r") as f:
                        if path.endswith(".yaml") or path.endswith(".yml"):
                            config = yaml.safe_load(f)
                        elif path.endswith(".json"):
                            config = json.load(f)
                        else:
                            continue

                        # 根据优先级更新配置
                        if priority == ConfigPriority.CRITICAL:
                            self.config.update(config)
                        else:
                            for key, value in config.items():
                                if key not in self.config:
                                    self.config[key] = value

        except Exception as e:
            self.logger.error(f"Error loading config files: {str(e)}")
            self.metrics.config_errors.inc()

    def _load_remote_configs(self):
        """加载远程配置"""
        try:
            remote_sources = self.base_config.get("remote_sources", [])

            for source in remote_sources:
                source_type = source["type"]
                if source_type == "etcd":
                    self._load_etcd_config(source)
                elif source_type == "consul":
                    self._load_consul_config(source)
                elif source_type == "redis":
                    self._load_redis_config(source)

        except Exception as e:
            self.logger.error(f"Error loading remote configs: {str(e)}")
            self.metrics.config_errors.inc()

    def _start_file_watchers(self):
        """启动文件监控"""
        try:
            config_files = self.base_config.get("config_files", [])

            for file_config in config_files:
                path = file_config["path"]
                if os.path.exists(path):
                    # 创建文件监控器
                    event_handler = ConfigFileHandler(self, path)
                    observer = Observer()
                    observer.schedule(
                        event_handler, os.path.dirname(path), recursive=False
                    )
                    observer.start()

                    self.watchers[path] = observer
                    self.handlers[path] = event_handler

        except Exception as e:
            self.logger.error(f"Error starting file watchers: {str(e)}")
            self.metrics.config_errors.inc()

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        try:
            # 首先检查缓存
            if key in self.config_cache:
                return self.config_cache[key]

            # 从配置中获取值
            value = self.config.get(key, default)

            # 更新缓存
            self.config_cache[key] = value

            return value

        except Exception as e:
            self.logger.error(f"Error getting config value for {key}: {str(e)}")
            return default

    def set(self, key: str, value: Any, source: ConfigSource = ConfigSource.FILE):
        """设置配置值"""
        try:
            # 更新配置
            self.config[key] = value

            # 清除缓存
            self.config_cache.pop(key, None)

            # 更新指标
            self.metrics.update_count.inc()
            self.metrics.last_update_time.set_to_current_time()
            self.metrics.active_configs.set(len(self.config))

            # 触发更新回调
            self._trigger_update_callbacks(key, value, source)

        except Exception as e:
            self.logger.error(f"Error setting config value for {key}: {str(e)}")
            self.metrics.config_errors.inc()

    def register_update_callback(self, callback, keys: Optional[List[str]] = None):
        """注册配置更新回调"""
        try:
            if keys is None:
                keys = ["*"]

            for key in keys:
                if key not in self.handlers:
                    self.handlers[key] = []
                self.handlers[key].append(callback)

        except Exception as e:
            self.logger.error(f"Error registering update callback: {str(e)}")

    def _trigger_update_callbacks(self, key: str, value: Any, source: ConfigSource):
        """触发配置更新回调"""
        try:
            # 触发特定键的回调
            callbacks = self.handlers.get(key, [])

            # 触发通配符回调
            callbacks.extend(self.handlers.get("*", []))

            # 执行回调
            for callback in callbacks:
                try:
                    callback(key, value, source)
                except Exception as e:
                    self.logger.error(f"Error in config update callback: {str(e)}")

        except Exception as e:
            self.logger.error(f"Error triggering update callbacks: {str(e)}")

    def reload(self):
        """重新加载配置"""
        try:
            # 备份当前配置
            old_config = self.config.copy()

            # 重新初始化配置
            self._init_config()

            # 找出变更的配置项
            changes = {}
            for key, value in self.config.items():
                if key not in old_config or old_config[key] != value:
                    changes[key] = value

            # 触发变更回调
            for key, value in changes.items():
                self._trigger_update_callbacks(key, value, ConfigSource.FILE)

            # 更新指标
            self.metrics.update_count.inc()
            self.metrics.last_update_time.set_to_current_time()

        except Exception as e:
            self.logger.error(f"Error reloading config: {str(e)}")
            self.metrics.config_errors.inc()

    def validate(self) -> bool:
        """验证配置"""
        try:
            # 验证必需的配置项
            required_keys = self.base_config.get("required_keys", [])
            for key in required_keys:
                if key not in self.config:
                    raise ValueError(f"Missing required config key: {key}")

            # 验证配置值类型
            type_specs = self.base_config.get("type_specs", {})
            for key, spec in type_specs.items():
                if key in self.config:
                    value = self.config[key]
                    if not isinstance(value, spec):
                        raise TypeError(
                            f"Invalid type for {key}: expected {spec}, got {type(value)}"
                        )

            # 验证值范围
            range_specs = self.base_config.get("range_specs", {})
            for key, spec in range_specs.items():
                if key in self.config:
                    value = self.config[key]
                    min_val = spec.get("min")
                    max_val = spec.get("max")
                    if min_val is not None and value < min_val:
                        raise ValueError(
                            f"Value for {key} is below minimum: {value} < {min_val}"
                        )
                    if max_val is not None and value > max_val:
                        raise ValueError(
                            f"Value for {key} is above maximum: {value} > {max_val}"
                        )

            return True

        except Exception as e:
            self.logger.error(f"Config validation error: {str(e)}")
            self.metrics.config_errors.inc()
            return False

    def get_all(self) -> Dict:
        """获取所有配置"""
        return self.config.copy()

    def get_metrics(self) -> Dict:
        """获取配置指标"""
        return {
            "update_count": self.metrics.update_count._value.get(),
            "error_count": self.metrics.config_errors._value.get(),
            "last_update_time": self.metrics.last_update_time._value.get(),
            "active_configs": self.metrics.active_configs._value.get(),
        }


class ConfigFileHandler(FileSystemEventHandler):
    """配置文件变更处理器"""

    def __init__(self, config_manager: ConfigManager, file_path: str):
        self.config_manager = config_manager
        self.file_path = file_path

    def on_modified(self, event):
        if event.src_path == self.file_path:
            self.config_manager.reload()

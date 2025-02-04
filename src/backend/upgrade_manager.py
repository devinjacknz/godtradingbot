import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pkg_resources
import requests
import yaml
from packaging import version


class UpgradeManager:
    """系统升级管理器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.backup_dir = Path(config.get("backup_dir", "backups"))
        self.upgrade_history_file = Path(
            config.get("upgrade_history_file", "upgrade_history.json")
        )
        self.requirements_file = Path(
            config.get("requirements_file", "requirements.txt")
        )
        self.db_config_file = Path(config.get("db_config_file", "database.yml"))

        # 创建备份目录
        self.backup_dir.mkdir(exist_ok=True)

        # 初始化升级历史
        self.upgrade_history = self._load_upgrade_history()

    def _load_upgrade_history(self) -> Dict[str, Any]:
        """加载升级历史"""
        if self.upgrade_history_file.exists():
            with open(self.upgrade_history_file) as f:
                return json.load(f)
        return {"upgrades": []}

    def _save_upgrade_history(self):
        """保存升级历史"""
        with open(self.upgrade_history_file, "w") as f:
            json.dump(self.upgrade_history, f, indent=2)

    def _backup_component(self, component: str):
        """备份组件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"{component}_{timestamp}"

        if component == "database":
            # 数据库备份
            with open(self.db_config_file) as f:
                db_config = yaml.safe_load(f)

            dump_cmd = f"pg_dump -U {db_config['username']} -d {db_config['database']} -f {backup_path}.sql"
            subprocess.run(dump_cmd, shell=True, check=True)

        elif component == "requirements":
            # 依赖包备份
            subprocess.run(f"pip freeze > {backup_path}.txt", shell=True, check=True)

        else:
            # 其他组件文件备份
            import shutil

            if os.path.exists(component):
                shutil.copy2(component, f"{backup_path}")

        return backup_path

    def check_dependencies(self) -> List[Dict[str, Any]]:
        """检查依赖包更新"""
        updates = []

        # 读取当前依赖
        with open(self.requirements_file) as f:
            current_requirements = {}
            for line in f:
                if "==" in line:
                    package, version = line.strip().split("==")
                    current_requirements[package] = version

        # 检查PyPI上的最新版本
        for package, current_version in current_requirements.items():
            try:
                response = requests.get(f"https://pypi.org/pypi/{package}/json")
                if response.status_code == 200:
                    latest_version = response.json()["info"]["version"]
                    if version.parse(latest_version) > version.parse(current_version):
                        updates.append(
                            {
                                "package": package,
                                "current_version": current_version,
                                "latest_version": latest_version,
                                "type": "dependency",
                            }
                        )
            except Exception as e:
                self.logger.warning(f"检查包 {package} 更新失败: {str(e)}")

        return updates

    def check_security_patches(self) -> List[Dict[str, Any]]:
        """检查安全补丁"""
        patches = []

        # 检查已知的安全漏洞
        try:
            response = requests.get("https://pypi.org/pypi/safety/json")
            if response.status_code == 200:
                safety_db = response.json()

                # 检查当前依赖包的安全问题
                for dist in pkg_resources.working_set:
                    package = dist.key
                    current_version = dist.version

                    # 在安全数据库中查找漏洞
                    if package in safety_db:
                        for vuln in safety_db[package]:
                            if version.parse(current_version) <= version.parse(
                                vuln["fixed_in"]
                            ):
                                patches.append(
                                    {
                                        "package": package,
                                        "current_version": current_version,
                                        "fixed_version": vuln["fixed_in"],
                                        "vulnerability": vuln["description"],
                                        "severity": vuln["severity"],
                                        "type": "security",
                                    }
                                )
        except Exception as e:
            self.logger.error(f"检查安全补丁失败: {str(e)}")

        return patches

    def check_api_versions(self) -> List[Dict[str, Any]]:
        """检查API版本"""
        updates = []

        # 检查配置的API端点
        api_endpoints = self.config.get("api_endpoints", {})
        for name, endpoint in api_endpoints.items():
            try:
                response = requests.get(f"{endpoint}/version")
                if response.status_code == 200:
                    api_version = response.json()["version"]
                    current_version = self.config.get("api_versions", {}).get(name)

                    if current_version and version.parse(api_version) > version.parse(
                        current_version
                    ):
                        updates.append(
                            {
                                "api": name,
                                "current_version": current_version,
                                "latest_version": api_version,
                                "type": "api",
                            }
                        )
            except Exception as e:
                self.logger.warning(f"检查API {name} 版本失败: {str(e)}")

        return updates

    def check_database_version(self) -> Optional[Dict[str, Any]]:
        """检查数据库版本"""
        try:
            # 读取数据库配置
            with open(self.db_config_file) as f:
                db_config = yaml.safe_load(f)

            # 连接数据库检查版本
            import psycopg2

            conn = psycopg2.connect(
                dbname=db_config["database"],
                user=db_config["username"],
                password=db_config["password"],
                host=db_config["host"],
                port=db_config["port"],
            )

            with conn.cursor() as cur:
                cur.execute("SHOW server_version;")
                current_version = cur.fetchone()[0]

                # 检查PostgreSQL最新版本
                response = requests.get("https://www.postgresql.org/versions.json")
                if response.status_code == 200:
                    latest_version = response.json()["latest"]["version"]

                    if version.parse(latest_version) > version.parse(current_version):
                        return {
                            "current_version": current_version,
                            "latest_version": latest_version,
                            "type": "database",
                        }

        except Exception as e:
            self.logger.error(f"检查数据库版本失败: {str(e)}")

        return None

    def perform_upgrade(self, upgrade_type: str, target: Dict[str, Any]) -> bool:
        """执行升级"""
        try:
            # 记录开始时间
            start_time = datetime.now()

            # 备份相关组件
            backup_path = self._backup_component(upgrade_type)

            success = False
            error_message = None

            if upgrade_type == "dependency":
                # 更新依赖包
                package = target["package"]
                version = target["latest_version"]
                try:
                    subprocess.run(
                        f"pip install {package}=={version}", shell=True, check=True
                    )
                    success = True
                except Exception as e:
                    error_message = str(e)

            elif upgrade_type == "security":
                # 应用安全补丁
                package = target["package"]
                version = target["fixed_version"]
                try:
                    subprocess.run(
                        f"pip install {package}=={version}", shell=True, check=True
                    )
                    success = True
                except Exception as e:
                    error_message = str(e)

            elif upgrade_type == "api":
                # 更新API版本配置
                api_name = target["api"]
                new_version = target["latest_version"]

                if "api_versions" not in self.config:
                    self.config["api_versions"] = {}
                self.config["api_versions"][api_name] = new_version

                # 保存配置
                with open("config.yml", "w") as f:
                    yaml.dump(self.config, f)
                success = True

            elif upgrade_type == "database":
                # 更新数据库版本
                # 注意: 数据库升级通常需要人工干预
                self.logger.warning("数据库升级需要人工操作，请参考升级文档")
                success = False
                error_message = "需要人工升级数据库"

            # 记录升级历史
            upgrade_record = {
                "type": upgrade_type,
                "target": target,
                "timestamp": start_time.isoformat(),
                "backup_path": str(backup_path),
                "success": success,
                "error": error_message,
            }

            self.upgrade_history["upgrades"].append(upgrade_record)
            self._save_upgrade_history()

            return success

        except Exception as e:
            self.logger.error(f"执行升级失败: {str(e)}")
            return False

    def rollback_upgrade(self, upgrade_record: Dict[str, Any]) -> bool:
        """回滚升级"""
        try:
            upgrade_type = upgrade_record["type"]
            backup_path = Path(upgrade_record["backup_path"])

            if upgrade_type == "database":
                # 恢复数据库
                with open(self.db_config_file) as f:
                    db_config = yaml.safe_load(f)

                restore_cmd = f"psql -U {db_config['username']} -d {db_config['database']} -f {backup_path}.sql"
                subprocess.run(restore_cmd, shell=True, check=True)

            elif upgrade_type == "requirements":
                # 恢复依赖包
                subprocess.run(
                    f"pip install -r {backup_path}.txt", shell=True, check=True
                )

            else:
                # 恢复其他组件文件
                import shutil

                target_path = upgrade_record["target"].get("path")
                if target_path and backup_path.exists():
                    shutil.copy2(backup_path, target_path)

            return True

        except Exception as e:
            self.logger.error(f"回滚升级失败: {str(e)}")
            return False

    def get_upgrade_status(self) -> Dict[str, Any]:
        """获取升级状态"""
        status = {
            "total_upgrades": len(self.upgrade_history["upgrades"]),
            "successful_upgrades": len(
                [u for u in self.upgrade_history["upgrades"] if u["success"]]
            ),
            "failed_upgrades": len(
                [u for u in self.upgrade_history["upgrades"] if not u["success"]]
            ),
            "last_upgrade": None,
            "pending_upgrades": {
                "dependencies": self.check_dependencies(),
                "security_patches": self.check_security_patches(),
                "api_versions": self.check_api_versions(),
                "database": self.check_database_version(),
            },
        }

        if self.upgrade_history["upgrades"]:
            status["last_upgrade"] = self.upgrade_history["upgrades"][-1]

        return status

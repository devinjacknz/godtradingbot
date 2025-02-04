import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, Dataset

from src.shared.config.ai_model import ModelConfig
from src.shared.models.deepseek import DeepSeek1_5B

# Model deployment mode (API first, local fallback)
AI_MODEL_MODE = os.getenv("AI_MODEL_MODE", "REMOTE")

# API configuration
API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-4ff47d34c52948edab6c9d0e7745b75b")

# Model endpoints
LOCAL_MODEL_ENDPOINT = "http://localhost:11434"
REMOTE_MODEL_ENDPOINT = os.getenv(
    "DEEPSEEK_API_URL", "https://api.deepseek.com/v3/completions"
)

# Model configurations
LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "deepseek-1.5b")
REMOTE_MODEL_NAME = os.getenv("DEEPSEEK_MODEL", "deepseek-1.5b")

# API configuration
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
TEMPERATURE = float(os.getenv("DEEPSEEK_TEMPERATURE", "0.7"))
MIN_CONFIDENCE = float(os.getenv("DEEPSEEK_MIN_CONFIDENCE", "0.7"))
MAX_RETRIES = int(os.getenv("DEEPSEEK_MAX_RETRIES", "3"))
RETRY_DELAY = float(os.getenv("DEEPSEEK_RETRY_DELAY", "2.0"))


class TradingDataset(Dataset):
    """交易数据集"""

    def __init__(self, features: np.ndarray, labels: np.ndarray):
        self.features = torch.FloatTensor(features)
        self.labels = torch.FloatTensor(labels)

    def __len__(self):
        return len(self.features)

    def __getitem__(self, idx):
        return self.features[idx], self.labels[idx]


class TradingModel(nn.Module):
    """交易模型"""

    def __init__(self, input_size: int, hidden_size: int = 128):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=2,
            batch_first=True,
            dropout=0.2,
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 64), nn.ReLU(), nn.Dropout(0.2), nn.Linear(64, 1)
        )

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        return self.fc(lstm_out[:, -1, :])


class ModelOptimizer:
    """AI模型优化器"""

    def __init__(self, config: ModelConfig):
        self.config = config
        self.model = None
        self.scaler = StandardScaler()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.llm = DeepSeek1_5B()
        self.history: List[Dict] = []

    def prepare_data(self, data: Dict[str, np.ndarray]) -> tuple:
        """准备训练数据

        Args:
            data: 原始数据

        Returns:
            tuple: (训练集, 验证集)
        """
        # 标准化特征
        features = self.scaler.fit_transform(data["features"])
        labels = data["labels"]

        # 划分训练集和验证集
        train_size = int(len(features) * 0.8)
        train_features = features[:train_size]
        train_labels = labels[:train_size]
        val_features = features[train_size:]
        val_labels = labels[train_size:]

        # 创建数据集
        train_dataset = TradingDataset(train_features, train_labels)
        val_dataset = TradingDataset(val_features, val_labels)

        # 创建数据加载器
        train_loader = DataLoader(
            train_dataset, batch_size=self.config.batch_size, shuffle=True
        )
        val_loader = DataLoader(val_dataset, batch_size=self.config.batch_size)

        return train_loader, val_loader

    def train(self, train_loader: DataLoader, val_loader: DataLoader):
        """训练模型

        Args:
            train_loader: 训练数据加载器
            val_loader: 验证数据加载器
        """
        input_size = next(iter(train_loader))[0].shape[-1]
        self.model = TradingModel(input_size).to(self.device)

        optimizer = torch.optim.Adam(
            self.model.parameters(), lr=self.config.learning_rate
        )
        criterion = nn.MSELoss()

        best_val_loss = float("inf")
        patience = self.config.patience
        patience_counter = 0

        for epoch in range(self.config.max_epochs):
            # 训练阶段
            self.model.train()
            train_loss = 0
            for features, labels in train_loader:
                features = features.to(self.device)
                labels = labels.to(self.device)

                optimizer.zero_grad()
                outputs = self.model(features)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()

                train_loss += loss.item()

            train_loss /= len(train_loader)

            # 验证阶段
            self.model.eval()
            val_loss = 0
            with torch.no_grad():
                for features, labels in val_loader:
                    features = features.to(self.device)
                    labels = labels.to(self.device)
                    outputs = self.model(features)
                    val_loss += criterion(outputs, labels).item()

            val_loss /= len(val_loader)

            # 记录训练历史
            self.history.append(
                {
                    "epoch": epoch + 1,
                    "train_loss": train_loss,
                    "val_loss": val_loss,
                    "timestamp": datetime.now(),
                }
            )

            # 早停检查
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                # 保存最佳模型
                torch.save(self.model.state_dict(), "best_model.pth")
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    print(f"Early stopping at epoch {epoch + 1}")
                    break

    def evaluate(self, test_loader: DataLoader) -> Dict[str, float]:
        """评估模型

        Args:
            test_loader: 测试数据加载器

        Returns:
            Dict: 评估指标
        """
        if not self.model:
            raise ValueError("Model not trained yet")

        self.model.eval()
        predictions = []
        actuals = []

        with torch.no_grad():
            for features, labels in test_loader:
                features = features.to(self.device)
                outputs = self.model(features)
                predictions.extend(outputs.cpu().numpy())
                actuals.extend(labels.numpy())

        predictions = np.array(predictions)
        actuals = np.array(actuals)

        # 计算评估指标
        mse = np.mean((predictions - actuals) ** 2)
        mae = np.mean(np.abs(predictions - actuals))
        r2 = 1 - np.sum((predictions - actuals) ** 2) / np.sum(
            (actuals - np.mean(actuals)) ** 2
        )

        return {"mse": mse, "mae": mae, "r2": r2}

    async def optimize_hyperparameters(self, data: Dict[str, np.ndarray]):
        """优化超参数

        Args:
            data: 训练数据
        """
        # 使用LLM生成超参数建议
        market_context = {
            "data_size": len(data["features"]),
            "feature_dim": data["features"].shape[1],
            "market_type": self.config.market_type,
            "volatility": np.std(data["labels"]),
        }

        param_suggestion = await self.llm.generate_hyperparameters(market_context)

        # 更新配置
        self.config.update(
            {
                "learning_rate": param_suggestion["learning_rate"],
                "batch_size": param_suggestion["batch_size"],
                "hidden_size": param_suggestion["hidden_size"],
            }
        )

    def get_training_summary(self) -> Dict[str, Any]:
        """获取训练总结"""
        if not self.history:
            return {}

        return {
            "total_epochs": len(self.history),
            "best_train_loss": min(h["train_loss"] for h in self.history),
            "best_val_loss": min(h["val_loss"] for h in self.history),
            "training_time": (
                self.history[-1]["timestamp"] - self.history[0]["timestamp"]
            ).total_seconds(),
            "early_stopped": len(self.history) < self.config.max_epochs,
        }

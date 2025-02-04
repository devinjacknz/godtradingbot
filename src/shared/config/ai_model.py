import os
from dataclasses import dataclass

AI_MODEL_MODE = os.getenv("AI_MODEL_MODE", "LOCAL")

# Model endpoints
LOCAL_MODEL_ENDPOINT = os.getenv("LOCAL_MODEL_ENDPOINT", "http://localhost:11434")

# Always use Docker service name when in container
if os.getenv("DOCKER_ENV") == "true":
    LOCAL_MODEL_ENDPOINT = "http://ollama:11434"
    print(f"Using Docker environment endpoint: {LOCAL_MODEL_ENDPOINT}")
elif os.getenv("LOCAL_MODEL_ENDPOINT"):
    LOCAL_MODEL_ENDPOINT = os.getenv("LOCAL_MODEL_ENDPOINT")
    print(f"Using custom environment endpoint: {LOCAL_MODEL_ENDPOINT}")

# Validate endpoint configuration
if not LOCAL_MODEL_ENDPOINT:
    raise ValueError("LOCAL_MODEL_ENDPOINT must be configured")

REMOTE_MODEL_ENDPOINT = os.getenv("REMOTE_MODEL_ENDPOINT", "https://api.deepseek.com")

# Model configurations
LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "deepseek-r1:1.5b")
REMOTE_MODEL_NAME = os.getenv("DEEPSEEK_MODEL", "deepseek-r1")

# API configuration
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
TEMPERATURE = float(os.getenv("DEEPSEEK_TEMPERATURE", "0.1"))
MIN_CONFIDENCE = float(os.getenv("DEEPSEEK_MIN_CONFIDENCE", "0.8"))
MAX_RETRIES = int(os.getenv("DEEPSEEK_MAX_RETRIES", "3"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
RETRY_DELAY = float(os.getenv("DEEPSEEK_RETRY_DELAY", "2.0"))


@dataclass
class DeepSeekModelConfig:
    MODEL_NAME: str = (
        LOCAL_MODEL_NAME if AI_MODEL_MODE == "LOCAL" else REMOTE_MODEL_NAME
    )
    QUANTIZATION: str = "4bit"
    BATCH_SIZE: int = 16
    MAX_SEQ_LEN: int = 2048
    DEVICE: str = "cuda:0"
    API_KEY: str = API_KEY
    TEMPERATURE: float = TEMPERATURE
    MIN_CONFIDENCE: float = MIN_CONFIDENCE
    MAX_RETRIES: int = MAX_RETRIES
    RETRY_DELAY: float = RETRY_DELAY
    REQUEST_TIMEOUT: int = REQUEST_TIMEOUT

    @property
    def is_quantized(self) -> bool:
        return self.QUANTIZATION == "4bit"


MODEL_CONFIG = DeepSeekModelConfig()

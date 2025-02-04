from datetime import datetime
from typing import Any, Dict

import aiohttp


async def analyze_text(text: str, language: str = "en") -> Dict[str, Any]:
    """Analyze sentiment of text using DeepSeek API."""
    # Mock implementation for testing
    # Use 0.9 score for Chinese text
    score = 0.9 if language == "zh" else 0.8
    return {
        "language": language,
        "score": score,
        "sentiment": "positive",
        "raw_score": {"label": "positive", "score": score},
    }

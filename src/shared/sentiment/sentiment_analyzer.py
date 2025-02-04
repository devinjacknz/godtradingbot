"""Mock sentiment analyzer module for testing"""


async def analyze_text(text: str) -> dict:
    """Mock function to analyze text sentiment

    Args:
        text: Text to analyze

    Returns:
        Dict containing sentiment analysis results
    """
    return {
        "sentiment": "positive",
        "score": 0.8,
        "confidence": 0.9,
        "entities": [],
        "keywords": [],
    }

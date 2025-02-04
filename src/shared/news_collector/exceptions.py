class NewsCollectorError(Exception):
    """Base exception for news collector errors."""

    pass


class SourceUnavailableError(NewsCollectorError):
    """Raised when a news source is unavailable."""

    pass


class ParseError(NewsCollectorError):
    """Raised when there's an error parsing news content."""

    pass

class AIError(Exception):
    """Base exception for AI-related errors."""

    pass


class ConfigError(Exception):
    """Base exception for configuration-related errors."""

    pass


class StrategyError(Exception):
    """Base exception for strategy-related errors."""

    pass


class ValidationError(Exception):
    """Base exception for validation-related errors."""

    pass


class APIError(Exception):
    """Base exception for API-related errors."""

    pass

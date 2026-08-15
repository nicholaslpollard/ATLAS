class AtlasError(Exception):
    """Base exception for ATLAS."""


class ConfigurationError(AtlasError):
    """Raised when ATLAS configuration is invalid or incomplete."""


class SecretNotFoundError(ConfigurationError):
    """Raised when a required secret is not available."""


class TimestampError(AtlasError):
    """Raised for invalid or ambiguous timestamps."""


class DataValidationError(AtlasError):
    """Raised when market or ingestion data violates a hard contract."""

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


class ProviderError(AtlasError):
    """Raised when an external data provider operation fails."""


class ProviderAccessDeniedError(ProviderError):
    """Raised when provider data exists but the current subscription cannot read it."""


class DownloadError(ProviderError):
    """Raised when a provider object cannot be downloaded safely."""


class ManifestError(AtlasError):
    """Raised when ingestion manifest state cannot be read or written."""

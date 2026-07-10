"""Shared core exceptions."""


class ProvenanceError(Exception):
    """Raised when export provenance verification fails."""


class ExportLoadError(Exception):
    """Raised when export files are missing, malformed, or incomplete."""


class CacheMissError(Exception):
    """Raised when an offline cache lookup misses."""


class ModelResponseError(Exception):
    """Raised when a model response is invalid or incomplete."""


class ConfigurationError(Exception):
    """Raised when factory or credential resolution fails before network I/O."""

"""Massive market-data provider adapters."""

from .client import MassiveS3Client
from .flat_files import MassiveFlatFileProvider
from .reference_data import MassiveReferenceProvider
from .rest import MassiveRESTClient

__all__ = ["MassiveS3Client", "MassiveFlatFileProvider", "MassiveReferenceProvider", "MassiveRESTClient"]

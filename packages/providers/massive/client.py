from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from packages.core.exceptions import ProviderAccessDeniedError, ProviderError
from packages.core.secrets import get_secret
from packages.core.settings import AtlasSettings


_ACCESS_DENIED_CODES = {"403", "AccessDenied", "Forbidden"}


class MassiveS3Client:
    """Thin S3-compatible client for Massive Flat Files.

    Credentials are read only from environment variables named in config.
    They are never embedded in URLs or log messages.
    """

    def __init__(self, settings: AtlasSettings, *, s3_client: Any | None = None) -> None:
        self.settings = settings
        self.bucket = settings.massive.provider.flat_file_bucket
        self.endpoint = settings.massive.provider.flat_file_endpoint
        self._client = s3_client or self._build_client()

    def _build_client(self) -> Any:
        creds = self.settings.massive.credentials
        access_key = get_secret(creds.s3_access_key_env)
        secret_key = get_secret(creds.s3_secret_key_env)
        session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        return session.client(
            "s3",
            endpoint_url=self.endpoint,
            config=Config(signature_version="s3v4", retries={"max_attempts": 0}),
        )

    @staticmethod
    def _is_access_denied(exc: ClientError) -> bool:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        return code in _ACCESS_DENIED_CODES or status == 403

    def list_objects(self, prefix: str) -> Iterator[dict[str, Any]]:
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    yield obj
        except (BotoCoreError, ClientError) as exc:
            raise ProviderError(f"Massive flat-file listing failed for prefix {prefix!r}: {type(exc).__name__}") from exc

    def can_read_object(self, remote_key: str) -> bool:
        """Probe actual subscription read access without downloading the full object.

        Massive can expose object names in listing results even when the account's
        historical entitlement does not permit GetObject for that date. A one-byte
        range read therefore distinguishes remote existence from readable access.
        """
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=remote_key, Range="bytes=0-0")
            body = response.get("Body")
            if body is not None:
                body.read(1)
                close = getattr(body, "close", None)
                if callable(close):
                    close()
            return True
        except ClientError as exc:
            if self._is_access_denied(exc):
                return False
            raise ProviderError(f"Massive flat-file access probe failed for {remote_key!r}: ClientError") from exc
        except (BotoCoreError, OSError) as exc:
            raise ProviderError(f"Massive flat-file access probe failed for {remote_key!r}: {type(exc).__name__}") from exc

    def iter_object_chunks(self, remote_key: str, chunk_size: int) -> Iterable[bytes]:
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=remote_key)
            body = response["Body"]
            while True:
                chunk = body.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        except ClientError as exc:
            if self._is_access_denied(exc):
                raise ProviderAccessDeniedError(
                    f"Massive denied flat-file read access for {remote_key!r}; the object may be outside the current subscription history window"
                ) from exc
            raise ProviderError(f"Massive flat-file read failed for {remote_key!r}: ClientError") from exc
        except (BotoCoreError, OSError) as exc:
            raise ProviderError(f"Massive flat-file read failed for {remote_key!r}: {type(exc).__name__}") from exc

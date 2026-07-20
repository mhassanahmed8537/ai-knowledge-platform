"""S3-compatible object storage (MinIO locally, S3 in AWS).

boto3 is synchronous; async callers should invoke these via ``asyncio.to_thread``.
"""

from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import ClientError

from core.config import get_settings


@lru_cache
def _client() -> Any:
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name="us-east-1",
    )


def ensure_bucket() -> None:
    client = _client()
    bucket = get_settings().s3_bucket
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        client.create_bucket(Bucket=bucket)


def build_key(org_id: object, document_id: object, filename: str) -> str:
    return f"orgs/{org_id}/documents/{document_id}/{filename}"


def upload_bytes(key: str, data: bytes, content_type: str | None = None) -> None:
    ensure_bucket()
    _client().put_object(
        Bucket=get_settings().s3_bucket,
        Key=key,
        Body=data,
        ContentType=content_type or "application/octet-stream",
    )


def download_bytes(key: str) -> bytes:
    obj = _client().get_object(Bucket=get_settings().s3_bucket, Key=key)
    body: bytes = obj["Body"].read()
    return body

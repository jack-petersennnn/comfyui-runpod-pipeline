"""
S3-compatible storage client for uploading workflow outputs.

Supports AWS S3, Cloudflare R2, MinIO, and any S3-compatible service.
Generates presigned URLs for result retrieval.
"""

import os
import logging
from typing import Optional

import boto3
from botocore.config import Config

logger = logging.getLogger("storage")

PRESIGNED_URL_EXPIRY = 3600 * 24  # 24 hours


class StorageClient:
    """Upload workflow outputs to S3-compatible storage."""

    def __init__(self):
        self.bucket = os.environ["S3_BUCKET"]
        self.endpoint = os.environ.get("S3_ENDPOINT")
        self.region = os.environ.get("S3_REGION", "auto")

        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=os.environ["S3_ACCESS_KEY"],
            aws_secret_access_key=os.environ["S3_SECRET_KEY"],
            region_name=self.region,
            config=Config(
                retries={"max_attempts": 3, "mode": "adaptive"},
                signature_version="s3v4",
            ),
        )

    def upload(
        self,
        data: bytes,
        key: str,
        content_type: str = "image/png",
    ) -> str:
        """
        Upload binary data to storage and return a presigned download URL.

        Args:
            data: File content bytes
            key: Storage object key (path)
            content_type: MIME type of the content

        Returns:
            Presigned URL for downloading the uploaded file
        """
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

        url = self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=PRESIGNED_URL_EXPIRY,
        )

        logger.info("Uploaded %s (%d bytes) to %s", key, len(data), self.bucket)
        return url

    def download(self, key: str) -> bytes:
        """Download an object from storage."""
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def exists(self, key: str) -> bool:
        """Check if an object exists in storage."""
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except self.client.exceptions.ClientError:
            return False

"""
Cloudinary raw file upload for backtest exports.

Uploads a local file (e.g. .xlsx) to Cloudinary and returns a direct URL.
Used as fallback when Google Sheets export fails (e.g. Drive quota exceeded).

Configuration (any of these works):
  - CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name  (auto-read by SDK)
  - OR set CLOUDINARY_CLOUD_NAME + CLOUDINARY_API_KEY + CLOUDINARY_API_SECRET
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)


def _do_upload(file_path: Path, public_id: str, cloud_name: str | None, api_key: str | None, api_secret: str | None) -> str:
    """Synchronous Cloudinary upload — run via run_in_executor."""
    import cloudinary
    import cloudinary.uploader

    # Configure only if explicit creds provided; CLOUDINARY_URL env var is auto-read otherwise
    if cloud_name and api_key and api_secret:
        cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret)

    response = cloudinary.uploader.upload(
        str(file_path),
        resource_type="raw",
        public_id=public_id,
        overwrite=True,
        use_filename=False,
    )
    return response["secure_url"]


async def upload_to_cloudinary(
    file_path: Path,
    public_id: str,
    cloudinary_url: str | None = None,
    cloud_name: str | None = None,
    api_key: str | None = None,
    api_secret: str | None = None,
) -> str:
    """
    Upload a file to Cloudinary as a raw resource.
    Returns the secure_url of the uploaded file.

    cloudinary_url takes precedence (set as CLOUDINARY_URL env var or passed directly).
    Falls back to cloud_name + api_key + api_secret if provided.
    """
    import os

    # If cloudinary_url is passed, set it as env var so the SDK picks it up
    if cloudinary_url:
        os.environ["CLOUDINARY_URL"] = cloudinary_url

    url = await asyncio.get_event_loop().run_in_executor(
        None, _do_upload, file_path, public_id, cloud_name, api_key, api_secret
    )

    log.info("backtest_cloudinary_upload_ok", public_id=public_id, url=url)
    return url

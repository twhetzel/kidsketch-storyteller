import asyncio
import logging
import aiohttp
from datetime import datetime, timezone
from urllib.parse import urlparse

from google.cloud import storage


def _created_metadata() -> dict:
    """Custom metadata to tag when content was uploaded (for bucket investigation)."""
    return {"x-created-date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


class StorageService:
    def __init__(self, bucket_name: str):
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)

    async def upload_file(self, local_path: str, remote_path: str) -> str:
        """
        Uploads a local file to GCS without blocking the event loop.
        Sets custom metadata x-created-date (UTC ISO) for bucket investigation.
        """
        blob = self.bucket.blob(remote_path)
        blob.metadata = _created_metadata()
        await asyncio.to_thread(blob.upload_from_filename, local_path)
        return f"https://storage.googleapis.com/{self.bucket.name}/{remote_path}"

    async def upload_bytes(self, data: bytes, remote_path: str, content_type: str = "image/png") -> str:
        """Uploads raw bytes to GCS; sets x-created-date metadata for bucket investigation."""
        blob = self.bucket.blob(remote_path)
        blob.metadata = _created_metadata()
        await asyncio.to_thread(blob.upload_from_string, data, content_type=content_type)
        return f"https://storage.googleapis.com/{self.bucket.name}/{remote_path}"

    async def download_file(self, remote_url: str, local_path: str):
        """
        Downloads a file from GCS or an external URL without blocking the event loop.
        For any storage.googleapis.com URL we use the GCS client (works with private buckets).
        """
        if "storage.googleapis.com" in remote_url and "/" in remote_url:
            # Parse bucket and path from https://storage.googleapis.com/bucket_name/path/to/object
            try:
                parsed = urlparse(remote_url)
                if parsed.netloc == "storage.googleapis.com" and parsed.path:
                    path_str = parsed.path.lstrip("/")
                    parts = path_str.split("/", 1)
                    if len(parts) == 2:
                        bucket_name, path = parts
                        bucket = self.client.bucket(bucket_name)
                        blob = bucket.blob(path)
                        await asyncio.to_thread(blob.download_to_filename, local_path)
                        return
            except Exception as e:
                logging.warning("GCS download from URL failed: %s", e)
            # Fall through to aiohttp if parse or download failed
        if f"/{self.bucket.name}/" in remote_url:
            # Our bucket — offload blocking SDK call to a thread
            path = remote_url.split(f"/{self.bucket.name}/")[-1].split("?")[0]
            blob = self.bucket.blob(path)
            await asyncio.to_thread(blob.download_to_filename, local_path)
        else:
            # External URL — use aiohttp for a fully async download
            async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
                async with session.get(remote_url) as response:
                    response.raise_for_status()
                    content = await response.read()
            await asyncio.to_thread(_write_bytes, local_path, content)

    async def download_text_with_generation(self, remote_path: str) -> tuple[str, int | None]:
        """
        Download the given object from this bucket as UTF-8 text and return it
        together with its current generation number. Raises FileNotFoundError
        if the object does not exist.
        """
        blob = await asyncio.to_thread(self.bucket.get_blob, remote_path)
        if blob is None:
            raise FileNotFoundError(f"GCS object not found: {remote_path}")
        data = await asyncio.to_thread(blob.download_as_bytes)
        return data.decode("utf-8"), blob.generation

    async def upload_text_with_generation(
        self,
        data: str,
        remote_path: str,
        generation: int | None,
        content_type: str = "application/json",
    ) -> int:
        """
        Upload UTF-8 text to GCS with optimistic locking based on the provided
        generation. When generation is None, this will only succeed if the
        object does not yet exist (if_generation_match = 0).
        Returns the new generation of the stored object.
        """
        blob = self.bucket.blob(remote_path)
        blob.metadata = _created_metadata()

        kwargs = {"content_type": content_type}
        if generation is None:
            # Only create if the object does not exist yet
            kwargs["if_generation_match"] = 0
        else:
            # Only succeed if the existing generation matches
            kwargs["if_generation_match"] = generation

        await asyncio.to_thread(blob.upload_from_string, data, **kwargs)
        return blob.generation


def _write_bytes(path: str, data: bytes) -> None:
    """Helper to write bytes to disk (called via asyncio.to_thread)."""
    with open(path, "wb") as f:
        f.write(data)

import asyncio
import aiohttp
from datetime import datetime, timezone
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
                after = remote_url.split("storage.googleapis.com/")[-1].split("?")[0]
                parts = after.split("/", 1)
                if len(parts) == 2:
                    bucket_name, path = parts
                    bucket = self.client.bucket(bucket_name)
                    blob = bucket.blob(path)
                    await asyncio.to_thread(blob.download_to_filename, local_path)
                    return
            except Exception as e:
                print(f"GCS download from URL failed: {e}")
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


def _write_bytes(path: str, data: bytes) -> None:
    """Helper to write bytes to disk (called via asyncio.to_thread)."""
    with open(path, "wb") as f:
        f.write(data)

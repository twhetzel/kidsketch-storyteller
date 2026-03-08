import asyncio
import aiohttp
from google.cloud import storage


class StorageService:
    def __init__(self, bucket_name: str):
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)

    async def upload_file(self, local_path: str, remote_path: str) -> str:
        """
        Uploads a local file to GCS without blocking the event loop.
        Note: Visibility for 'Uniform' buckets must be set via IAM on the bucket.
        """
        blob = self.bucket.blob(remote_path)
        await asyncio.to_thread(blob.upload_from_filename, local_path)
        return f"https://storage.googleapis.com/{self.bucket.name}/{remote_path}"

    async def upload_bytes(self, data: bytes, remote_path: str, content_type: str = "image/png") -> str:
        """Uploads raw bytes to GCS without blocking the event loop."""
        blob = self.bucket.blob(remote_path)
        await asyncio.to_thread(blob.upload_from_string, data, content_type=content_type)
        return f"https://storage.googleapis.com/{self.bucket.name}/{remote_path}"

    async def download_file(self, remote_url: str, local_path: str):
        """
        Downloads a file from GCS or an external URL without blocking the event loop.
        """
        if f"/{self.bucket.name}/" in remote_url:
            # GCS path — offload blocking SDK call to a thread
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

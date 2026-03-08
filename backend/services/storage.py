import os
from google.cloud import storage

class StorageService:
    def __init__(self, bucket_name: str):
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)

    async def upload_file(self, local_path: str, remote_path: str) -> str:
        """
        Uploads a local file to GCS.
        Note: Visibility for 'Uniform' buckets must be set via IAM on the bucket.
        """
        blob = self.bucket.blob(remote_path)
        blob.upload_from_filename(local_path)
        return f"https://storage.googleapis.com/{self.bucket.name}/{remote_path}"

    async def upload_bytes(self, data: bytes, remote_path: str, content_type: str = "image/png") -> str:
        blob = self.bucket.blob(remote_path)
        blob.upload_from_string(data, content_type=content_type)
        return f"https://storage.googleapis.com/{self.bucket.name}/{remote_path}"

    async def download_file(self, remote_url: str, local_path: str):
        """
        Downloads a file from GCS or an external URL.
        """
        # If it's a GCS URL belonging to our bucket
        if f"/{self.bucket.name}/" in remote_url:
            path = remote_url.split(f"/{self.bucket.name}/")[-1]
            # Handle potential query params in URL
            path = path.split("?")[0]
            blob = self.bucket.blob(path)
            blob.download_to_filename(local_path)
        else:
            # Fallback for external URLs (like placeholders)
            import urllib.request
            opener = urllib.request.build_opener()
            opener.addheaders = [('User-agent', 'Mozilla/5.0')]
            with opener.open(remote_url) as response, open(local_path, 'wb') as out_file:
                out_file.write(response.read())

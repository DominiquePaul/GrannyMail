from datetime import datetime
from abc import ABC, abstractmethod
from supabase import Client  # create_client
import grannymail.config as cfg


class BlobRepositoryBase(ABC):
    @abstractmethod
    def create_blob_path(self, user_id: str) -> str:
        pass

    @abstractmethod
    def upload(self, bytes: bytes, blob_path: str, mime_type: str):
        pass

    @abstractmethod
    def download(self, blob_path: str) -> bytes:
        pass


class SupabaseBlobStorage(BlobRepositoryBase):
    def __init__(self, client: Client):
        if type(self) is SupabaseBlobStorage:
            raise TypeError(
                "SupabaseBlobStorage is an abstract class and cannot be instantiated directly"
            )
        self.client = client
        self.bucket: str = cfg.SUPABASE_BUCKET_NAME
        self.blob_prefix: str
        self.blob_manager = self.client.storage.from_(self.bucket)

    def _get_suffix(self, mime_type: str) -> str:
        if mime_type == "audio/ogg":
            return ".ogg"
        elif mime_type == "application/pdf":
            return ".pdf"
        else:
            raise ValueError(f"mime_type {mime_type} not supported for file upload")

    def create_blob_path(self, user_id: str) -> str:
        return f"{self.blob_prefix}/{user_id}/{datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')}"

    def upload(self, bytes: bytes, blob_path: str, mime_type: str):
        blob_path += self._get_suffix(mime_type)
        self.blob_manager.upload(
            file=bytes, path=blob_path, file_options={"content-type": mime_type}
        )

    def download(self, blob_path: str) -> bytes:
        return self.blob_manager.download(blob_path)


class DraftBlobRepository(SupabaseBlobStorage):
    def __init__(self, client: Client):
        super().__init__(client)
        self.bucket: str = cfg.SUPABASE_BUCKET_NAME
        self.blob_prefix: str = "drafts"


class FilesBlobRepository(SupabaseBlobStorage):
    def __init__(self, client: Client):
        super().__init__(client)
        self.bucket: str = cfg.SUPABASE_BUCKET_NAME
        self.blob_prefix: str = "memos"

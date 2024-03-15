from abc import ABC, abstractmethod

from supabase import Client  # create_client

import grannymail.config as cfg
from grannymail.utils import utils


class BlobRepositoryBase(ABC):
    blob_prefix: str

    def _create_blob_path(self, user_id: str, mime_type: str) -> str:

        file_path = f"{self.blob_prefix}/{user_id}/{utils.get_utc_timestamp()}"
        if mime_type == "audio/ogg":
            suffix = ".ogg"
        elif mime_type == "application/pdf":
            suffix = ".pdf"
        else:
            raise ValueError(f"mime_type {mime_type} not supported for file upload")

        return file_path + suffix

    @abstractmethod
    def upload(self, bytes: bytes, user_id: str, mime_type: str) -> str:
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

    def upload(self, bytes: bytes, user_id: str, mime_type: str) -> str:
        blob_path = self._create_blob_path(user_id, mime_type)
        self.blob_manager.upload(
            file=bytes, path=blob_path, file_options={"content-type": mime_type}
        )
        return blob_path

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

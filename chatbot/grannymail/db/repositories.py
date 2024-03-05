from datetime import datetime
from postgrest._sync.request_builder import SyncSelectRequestBuilder
import typing as t
from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from . import classes as dbc
import supabase
from supabase import create_client, Client
from dataclasses import asdict
import grannymail.config as cfg


T = TypeVar("T", bound=dbc.AbstractDataTableClass)


class DuplicateEntryError(Exception):
    """Exception raised for errors in the insertion of an entry that already exists."""

    def __init__(self, message="Duplicate entry is not allowed"):
        self.message = message
        super().__init__(self.message)


def create_supabase_client() -> Client:
    return create_client(cfg.SUPABASE_URL, cfg.SUPABASE_KEY)


class RepositoryBase(ABC, Generic[T]):
    @abstractmethod
    def add(self, entity: T) -> T:
        """Adds a new entity to the repository."""
        pass

    @abstractmethod
    def get(
        self,
        id: str | None,
        filters: dict[str, t.Any] = {},
        order: dict[str, t.Literal["asc", "desc"]] = {},
    ) -> T:
        """Retrieves an entity by its ID."""
        pass

    @abstractmethod
    def get_all(
        self,
        filters: dict[str, t.Any] = {},
        order: dict[str, t.Literal["asc", "desc"]] = {},
    ) -> list[T]:
        """Retrieves all entities from the repository."""
        pass

    @abstractmethod
    def update(self, entity: T) -> T:
        """Updates an existing entity in the repository."""
        pass

    @abstractmethod
    def delete(self, id: str) -> None:
        """Deletes an entity from the repository."""
        pass


class BlobRepositoryBase(ABC):
    @abstractmethod
    def upload(self, bytes: bytes, filename: str, mime_type: str) -> str:
        pass

    @abstractmethod
    def download(self, filename: str) -> bytes:
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

    def create_file_path(self, user_id: str) -> str:
        return f"{self.blob_prefix}/{user_id}/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"

    def upload(self, bytes: bytes, blob_path: str, mime_type: str) -> str:
        blob_path += self._get_suffix(mime_type)
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


class SupabaseRepository(RepositoryBase[T]):
    def __init__(self, client: Client):
        if type(self) is SupabaseRepository:
            raise TypeError(
                "SupabaseRepository is an abstract class and cannot be instantiated directly"
            )
        self.client = client
        # Initialize these in child classes
        self.__table__: str = ""
        self.__id_col__: str = ""
        self.__data_type__: t.Type[T]

    def add(self, entity: T) -> T:
        try:
            resp = self.client.table(self.__table__).insert(asdict(entity)).execute()
        except supabase.PostgrestAPIError as e:
            if e.code == "23505":
                raise DuplicateEntryError(
                    f"Failed to add entity: {e.message}. {e.details}"
                )
            else:
                raise e
        # Use cast to inform the type checker of the return type
        return t.cast(T, self.__data_type__(**resp.data[0]))

    # return self.__data_type__(**resp.data[0])

    def _get(
        self, filters: dict[str, t.Any], order: dict[str, t.Literal["asc", "desc"]]
    ) -> SyncSelectRequestBuilder:
        query = self.client.table(self.__table__).select("*")
        for k, v in filters.items():
            query = query.eq(k, v)
        for k, v in order.items():
            query = query.order(k, desc=True if v == "desc" else False)
        return query

    def maybe_get_one(
        self,
        id: str | None,
        filters: dict[str, t.Any] = {},
        order: dict[str, t.Literal["asc", "desc"]] = {},
    ) -> T | None:
        if id is None and filters == {}:
            raise ValueError("Need to provide either filters or id")
        filters[self.__id_col__] = id
        query = self._get(filters, order)
        response = query.maybe_single().execute()
        if response is None:
            return None
        else:
            # Assuming child classes have a constructor that accepts **kwargs
            # This might need adjustment based on your model constructors
            return self.__data_type__(**response.data)

    def get(
        self,
        id: str | None,
        filters: dict[str, t.Any] = {},
        order: dict[str, t.Literal["asc", "desc"]] = {},
    ) -> T:
        if id is None and filters == {}:
            raise ValueError("Need to provide either filters or id")
        filters[self.__id_col__] = id
        query = self._get(filters, order)
        response = query.execute()
        return t.cast(T, self.__data_type__(**response.data[0]))

    def get_all(
        self,
        filters: dict[str, t.Any] = {},
        order: dict[str, t.Literal["asc", "desc"]] = {},
    ) -> list[T]:
        response = self._get(filters, order).execute()
        return [self.__data_type__(**r) for r in response.data]

    def update(self, entity: T) -> T:
        # assert isinstance(entity, DataclassInstance), "Entity must be a dataclass"
        r = (
            self.client.table(self.__table__)
            .update(asdict(entity))
            .eq("user_id", getattr(entity, self.__id_col__))
            .execute()
        )
        return self.__data_type__(**r.data[0])

    def delete(self, id: str) -> None:
        self.client.table(self.__table__).delete().eq(self.__id_col__, id).execute()


class UserRepository(SupabaseRepository[dbc.User]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "users"
        self.__id_col__: str = "user_id"
        self.__data_type__ = dbc.User


class MessagesRepository(SupabaseRepository[dbc.Message]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "messages"
        self.__id_col__: str = "message_id"
        self.__data_type__ = dbc.Message


class TelegramMessagesRepository(SupabaseRepository[dbc.TelegramMessage]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "messages"
        self.__id_col__: str = "message_id"
        self.__data_type__ = dbc.TelegramMessage


class WhatsappMessagesRepository(SupabaseRepository[dbc.WhatsappMessage]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "messages"
        self.__id_col__: str = "message_id"
        self.__data_type__ = dbc.WhatsappMessage


class FileRepository(SupabaseRepository[dbc.File]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "files"
        self.__id_col__: str = "file_id"
        self.__data_type__ = dbc.File


class AddressRepository(SupabaseRepository[dbc.Address]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "addresses"
        self.__id_col__: str = "address_id"
        self.__data_type__ = dbc.Address

    def get_user_addresses(self, user_id: str) -> list[dbc.Address]:
        return self.get_all(filters={"user_id": user_id}, order={"created_at": "asc"})


class DraftRepository(SupabaseRepository[dbc.Draft]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "drafts"
        self.__id_col__: str = "draft_id"
        self.__data_type__ = dbc.Draft


class OrderRepository(SupabaseRepository[dbc.Order]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "orders"
        self.__id_col__: str = "order_id"
        self.__data_type__ = dbc.Order


class Attachmentepository(SupabaseRepository[dbc.Attachment]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "attachments"
        self.__id_col__: str = "attachment_id"
        self.__data_type__ = dbc.Attachment


class SystemMessageRepository(SupabaseRepository[dbc.SystemMessage]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "system_messages"
        self.__id_col__: str = "message_identifier"
        self.__data_type__ = dbc.SystemMessage

    def get_msg(self, message_identifier: str) -> str:
        return self.get(message_identifier).message_body

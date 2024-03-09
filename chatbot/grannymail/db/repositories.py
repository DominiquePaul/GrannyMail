from postgrest._sync.request_builder import SyncSelectRequestBuilder
import typing as t
from abc import ABC, abstractmethod
from typing import Generic, TypeVar
import supabase
from supabase import Client
from dataclasses import asdict

from grannymail.domain import models as m

T = TypeVar("T", bound=m.AbstractDataTableClass)


class DuplicateEntryError(Exception):
    """Exception raised for errors in the insertion of an entry that already exists."""

    def __init__(self, message="Duplicate entry is not allowed"):
        self.message = message
        super().__init__(self.message)


# def create_supabase_client() -> Client:
#     return create_client(cfg.SUPABASE_URL, cfg.SUPABASE_KEY)


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
    def maybe_get_one(
        self,
        id: str | None,
        filters: dict[str, t.Any] = {},
        order: dict[str, t.Literal["asc", "desc"]] = {},
    ) -> T | None:
        pass

    @abstractmethod
    def get_one(
        self,
        id: str | None,
        filters: dict[str, t.Any] = {},
        order: dict[str, t.Literal["asc", "desc"]] = {},
    ) -> T:
        """Expects to return and only one result. Otherwise raises an error."""
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


class SystemsMessageRepositoryBase(RepositoryBase):
    @abstractmethod
    def get_msg(self, id: str) -> str:
        """Retrieves the message body by its ID."""
        pass


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
        return self.__data_type__(**resp.data[0])

    def _get(
        self, filters: dict[str, t.Any], order: dict[str, t.Literal["asc", "desc"]]
    ) -> SyncSelectRequestBuilder:
        if id is None and filters == {}:
            raise ValueError("Need to provide either filters or id")
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
        filters[self.__id_col__] = id
        query = self._get(filters, order)
        response = query.maybe_single().execute()
        if response is None:
            return None
        else:
            return self.__data_type__(**response.data)

    def get_one(
        self,
        id: str | None,
        filters: dict[str, t.Any] = {},
        order: dict[str, t.Literal["asc", "desc"]] = {},
    ) -> T:
        filters[self.__id_col__] = id
        query = self._get(filters, order)
        response = query.single().execute()
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


class UserRepository(SupabaseRepository[m.User]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "users"
        self.__id_col__: str = "user_id"
        self.__data_type__ = m.User


class MessageRepository(SupabaseRepository[m.Message]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "messages"
        self.__id_col__: str = "message_id"
        self.__data_type__ = m.Message


class TelegramMessageRepository(SupabaseRepository[m.TelegramMessage]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "messages"
        self.__id_col__: str = "message_id"
        self.__data_type__ = m.TelegramMessage


class WhatsAppMessageRepository(SupabaseRepository[m.WhatsappMessage]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "messages"
        self.__id_col__: str = "message_id"
        self.__data_type__ = m.WhatsappMessage


class FileRepository(SupabaseRepository[m.File]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "files"
        self.__id_col__: str = "file_id"
        self.__data_type__ = m.File


class AddressRepository(SupabaseRepository[m.Address]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "addresses"
        self.__id_col__: str = "address_id"
        self.__data_type__ = m.Address

    def get_user_addresses(self, user_id: str) -> list[m.Address]:
        return self.get_all(filters={"user_id": user_id}, order={"created_at": "asc"})


class DraftRepository(SupabaseRepository[m.Draft]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "drafts"
        self.__id_col__: str = "draft_id"
        self.__data_type__ = m.Draft


class OrderRepository(SupabaseRepository[m.Order]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "orders"
        self.__id_col__: str = "order_id"
        self.__data_type__ = m.Order


class AttachmentRepository(SupabaseRepository[m.Attachment]):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "attachments"
        self.__id_col__: str = "attachment_id"
        self.__data_type__ = m.Attachment


class SystemMessageRepository(
    SystemsMessageRepositoryBase, SupabaseRepository[m.SystemMessage]
):
    def __init__(self, client: Client):
        super().__init__(client)
        self.__table__: str = "system_messages"
        self.__id_col__: str = "message_identifier"
        self.__data_type__ = m.SystemMessage

    def get_msg(self, message_identifier: str) -> str:
        return self.get(message_identifier).message_body

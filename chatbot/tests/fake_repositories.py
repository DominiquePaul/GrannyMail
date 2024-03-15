import typing as t

import grannymail.domain.models as m
from grannymail.db.blob_repos import BlobRepositoryBase
from grannymail.db.repositories import (
    RepositoryBase,
    SystemMessageRepository,
    SystemsMessageRepositoryBase,
    T,
)
from grannymail.services.unit_of_work import AbstractUnitOfWork, SupabaseUnitOfWork
from grannymail.utils import utils


class FakeRepoBase(RepositoryBase[T]):
    def __init__(self, id_attr: str):
        self._batches: set[T] = set()
        self._id_attr: str = id_attr

    def add(self, entity: T) -> T:
        """Adds a new entity to the repository."""
        self._batches.add(entity)
        return entity

    def _get(
        self, filters: dict[str, t.Any], order: dict[str, t.Literal["asc", "desc"]]
    ):
        if not filters:
            raise ValueError("Filters must be provided")
        results = [
            entity
            for entity in self._batches
            if all(
                getattr(entity, key, None) == value for key, value in filters.items()
            )
        ]
        for key, direction in order.items():
            results.sort(key=lambda x: getattr(x, key, 0), reverse=direction == "desc")
        if not results:
            return None
        return results[0]

    def maybe_get_one(
        self,
        id: str | None,
        filters: t.Optional[dict[str, t.Any]] = None,
        order: t.Optional[dict[str, t.Literal["asc", "desc"]]] = None,
    ) -> T | None:
        if filters is None:
            filters = {}
        if order is None:
            order = {}
        if id is not None:
            filters[self._id_attr] = id
        return self._get(filters=filters, order=order)

    def get_one(
        self,
        id: str | None,
        filters: t.Optional[dict[str, t.Any]] = None,
        order: t.Optional[dict[str, t.Literal["asc", "desc"]]] = None,
    ) -> T:
        if filters is None:
            filters = {}
        if order is None:
            order = {}
        if id is not None:
            filters[self._id_attr] = id
        out = self._get(filters=filters, order=order)
        if out is None:
            raise ValueError("Entity not found")
        return out

    def get_all(
        self,
        filters: t.Optional[dict[str, t.Any]] = None,
        order: t.Optional[dict[str, t.Literal["asc", "desc"]]] = None,
    ) -> list[T]:
        if filters is None:
            filters = {}
        if order is None:
            order = {}
        results = list(self._batches)
        if filters:
            results = [
                entity
                for entity in results
                if all(getattr(entity, k, None) == v for k, v in filters.items())
            ]
        if order:
            for key, direction in reversed(order.items()):
                results.sort(
                    key=lambda x: getattr(x, key, 0), reverse=(direction == "desc")
                )
        return results

    def update(self, entity: T) -> T:
        """Updates an existing entity in the repository."""
        try:
            self._batches.remove(entity)
        except KeyError:
            raise ValueError("Entity not found in the repository.")
        self._batches.add(entity)
        return entity

    def delete(self, id: str) -> None:
        """Deletes an entity from the repository."""
        entity_to_delete = None
        for entity in self._batches:
            if getattr(entity, self._id_attr, None) == id:
                entity_to_delete = entity
                break
        if entity_to_delete:
            self._batches.remove(entity_to_delete)
        else:
            raise ValueError(
                "Entity with id {} not found in the repository.".format(id)
            )


def create_fake_repo(class_type, id_attr: str):
    class FakeRepo(FakeRepoBase[class_type]):
        pass

    return FakeRepo(id_attr=id_attr)


class FakeBlobRepo(BlobRepositoryBase):
    def __init__(self, blob_prefix: str):
        self._blobs: dict[str, bytes] = {}
        self.blob_prefix: str = blob_prefix

    def upload(self, bytes: bytes, user_id: str, mime_type: str):
        # Implement upload logic or leave as a pass for a fake implementation
        blob_path = self._create_blob_path(user_id, mime_type)
        self._blobs[blob_path] = bytes
        return blob_path

    def download(self, blob_path: str) -> bytes:
        return self._blobs[blob_path]


class FakeUnitOfWork(AbstractUnitOfWork):
    def __init__(self):
        self.users = create_fake_repo(m.User, "user_id")
        self.messages = create_fake_repo(m.BaseMessage, "message_id")
        self.tg_messages = self.messages
        self.wa_messages = self.messages
        self.files = create_fake_repo(m.File, "file_id")
        self.addresses = create_fake_repo(m.Address, "address_id")
        self.drafts = create_fake_repo(m.Draft, "draft_id")
        self.orders = create_fake_repo(m.Order, "order_id")
        self.attachments = create_fake_repo(m.Attachment, "attachment_id")
        self.system_messages = SystemMessageRepository(
            SupabaseUnitOfWork().create_client()
        )
        self.drafts_blob = FakeBlobRepo("drafts")
        self.files_blob = FakeBlobRepo("files")

    def __enter__(self):
        return super().__enter__()

    def commit(self):
        """Currently a placeholder as Supabase does not support transactions."""
        pass

    def rollback(self):
        """Currently a placeholder as Supabase does not support transactions."""
        pass

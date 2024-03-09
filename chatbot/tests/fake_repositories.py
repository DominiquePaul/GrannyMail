import datetime
import typing as t
import grannymail.domain.models as m
from grannymail.db.repositories import RepositoryBase, SystemsMessageRepositoryBase, T
from grannymail.db.blob_repos import BlobRepositoryBase
from grannymail.services.unit_of_work import AbstractUnitOfWork


class FakeRepoBase(RepositoryBase[T]):
    def __init__(self):
        self._batches = set()

    def add(self, entity: T) -> T:
        """Adds a new entity to the repository."""
        self._batches.add(entity)
        return entity

    def get(
        self,
        id: str | None,
        filters: dict[str, t.Any] = {},
        order: dict[str, t.Literal["asc", "desc"]] = {},
    ) -> T:
        """Retrieves an entity by its ID."""
        if id is not None:
            for entity in self._batches:
                if getattr(entity, "id", None) == id:
                    return entity
        if filters:
            for entity in self._batches:
                if all(getattr(entity, k, None) == v for k, v in filters.items()):
                    return entity
        raise ValueError("Entity not found")

    def maybe_get_one(
        self,
        id: str | None,
        filters: dict[str, t.Any] = {},
        order: dict[str, t.Literal["asc", "desc"]] = {},
    ) -> T | None:
        try:
            return self.get(id=id, filters=filters, order=order)
        except ValueError:
            return None

    def get_one(
        self,
        id: str | None,
        filters: dict[str, t.Any] = {},
        order: dict[str, t.Literal["asc", "desc"]] = {},
    ) -> T:
        """Expects to return and only one result. Otherwise raises an error."""
        results = self.get_all(filters=filters, order=order)
        if id is not None:
            results = [
                result for result in results if getattr(result, "id", None) == id
            ]
        if len(results) != 1:
            raise ValueError("Expected exactly one result, got {}".format(len(results)))
        return results[0]

    def get_all(
        self,
        filters: dict[str, t.Any] = {},
        order: dict[str, t.Literal["asc", "desc"]] = {},
    ) -> list[T]:
        """Retrieves all entities from the repository."""
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
            if getattr(entity, "id", None) == id:
                entity_to_delete = entity
                break
        if entity_to_delete:
            self._batches.remove(entity_to_delete)
        else:
            raise ValueError(
                "Entity with id {} not found in the repository.".format(id)
            )


class FakeSystemMessageRepo(
    SystemsMessageRepositoryBase, FakeRepoBase[m.SystemMessage]
):
    def get_msg(self, msg_key: str) -> str:
        """Retrieves a system message based on its key."""
        message = next(
            (msg for msg in self._batches if msg.message_identifier == msg_key), None
        )
        if not message:
            raise ValueError(f"Message with key {msg_key} not found.")
        return message.message_body


def create_fake_repo(class_type):
    class FakeRepo(FakeRepoBase[class_type]):
        pass

    return FakeRepo()


class FakeBlobRepo(BlobRepositoryBase):
    def __init__(self, blob_prefix):

        self._blobs = {}
        self.blob_prefix: str = blob_prefix

    def create_blob_path(self, user_id: str) -> str:
        # Implement according to your logic or return a mock path
        return f"{self.blob_prefix}/{user_id}/{datetime.datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')}"

    def upload(self, bytes: bytes, blob_path: str, mime_type: str):
        # Implement upload logic or leave as a pass for a fake implementation
        self._blobs[blob_path] = bytes

    def download(self, blob_path: str) -> bytes:
        return self._blobs[blob_path]


class FakeUnitOfWork(AbstractUnitOfWork):
    def __enter__(self):

        self.users = create_fake_repo(m.User)
        self.messages = create_fake_repo(m.Message)
        self.tg_messages = create_fake_repo(m.TelegramMessage)
        self.wa_messages = create_fake_repo(m.WhatsappMessage)
        self.files = create_fake_repo(m.File)
        self.addresses = create_fake_repo(m.Address)
        self.drafts = create_fake_repo(m.Draft)
        self.orders = create_fake_repo(m.Order)
        self.attachments = create_fake_repo(m.Attachment)
        self.system_messages = FakeSystemMessageRepo()
        self.drafts_blob = FakeBlobRepo("drafts")
        self.files_blob = FakeBlobRepo("files")
        return super().__enter__()

    def commit(self):
        """Currently a placeholder as Supabase does not support transactions."""
        pass

    def rollback(self):
        """Currently a placeholder as Supabase does not support transactions."""
        pass

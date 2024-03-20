import abc
from typing import Callable

import supabase

import grannymail.config as cfg
import grannymail.db.blob_repos as blob_repos
import grannymail.db.repositories as repos
from grannymail.domain import models as m


class AbstractUnitOfWork(abc.ABC):
    """
    An abstract base class defining the Unit of Work pattern interface.
    This class declares common repository attributes and the essential methods for transaction management.
    """

    users: repos.RepositoryBase[m.User]
    messages: repos.RepositoryBase[m.BaseMessage]
    tg_messages: repos.RepositoryBase[m.TelegramMessage]
    wa_messages: repos.RepositoryBase[m.WhatsappMessage]
    files: repos.RepositoryBase[m.File]
    addresses: repos.RepositoryBase[m.Address]
    drafts: repos.RepositoryBase[m.Draft]
    orders: repos.RepositoryBase[m.Order]
    attachments: repos.RepositoryBase[m.Attachment]
    system_messages: repos.SystemsMessageRepositoryBase
    drafts_blob: blob_repos.BlobRepositoryBase
    files_blob: blob_repos.BlobRepositoryBase

    def __init__(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.rollback()

    @abc.abstractmethod
    def commit(self):
        """Commits the current transaction."""
        raise NotImplementedError

    @abc.abstractmethod
    def rollback(self):
        """Rolls back the current transaction."""
        raise NotImplementedError


class SupabaseUnitOfWork(AbstractUnitOfWork):
    """
    A concrete implementation of the Unit of Work pattern using Supabase.
    As Supabase does not support transactions, this class is prepared for future database replacements.

    Going forward, it could make sense to investigate
        1) Blob storage: using domain events to trigger blob storage
        events and thereby increase decoupling
        2) Implement Compensating Actions for Blob Storage
        3) Investigate the "Saga Pattern" further
    """

    def __init__(self) -> None:
        self.session_factory: Callable = self.create_client

    @staticmethod
    def create_client() -> supabase.Client:  # type: ignore
        """Creates and returns a Supabase client using the application configuration."""
        return supabase.create_client(cfg.SUPABASE_URL, cfg.SUPABASE_KEY)  # type: ignore

    def __enter__(self):
        client = self.session_factory()

        self.users = repos.UserRepository(client)
        self.messages = repos.MessageRepository(client)
        self.tg_messages = repos.TelegramMessageRepository(client)
        self.wa_messages = repos.WhatsAppMessageRepository(client)
        self.files = repos.FileRepository(client)
        self.addresses = repos.AddressRepository(client)
        self.drafts = repos.DraftRepository(client)
        self.orders = repos.OrderRepository(client)
        self.attachments = repos.AttachmentRepository(client)
        self.system_messages = repos.SystemMessageRepository(client)
        self.drafts_blob = blob_repos.DraftBlobRepository(client)
        self.files_blob = blob_repos.FilesBlobRepository(client)
        return super().__enter__()

    def commit(self):
        """Currently a placeholder as Supabase does not support transactions."""
        pass

    def rollback(self):
        """Currently a placeholder as Supabase does not support transactions."""
        pass

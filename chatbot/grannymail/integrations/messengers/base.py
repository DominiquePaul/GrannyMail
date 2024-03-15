from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from grannymail.domain import models as m
from grannymail.services.unit_of_work import AbstractUnitOfWork


class AbstractMessenger(ABC, Generic[m.MessageType]):
    @abstractmethod
    async def reply_text(
        self, ref_message: m.MessageType, message_body: str, uow: AbstractUnitOfWork
    ) -> m.MessageType:
        """
        Send a text message to the recipient.
        """
        pass

    @abstractmethod
    async def reply_document(
        self,
        ref_message: m.MessageType,
        file_data: bytes,
        filename: str,
        mime_type: str,
        uow: AbstractUnitOfWork,
    ) -> m.MessageType:
        pass

    @abstractmethod
    async def reply_buttons(
        self,
        ref_message: m.MessageType,
        main_msg: str,
        cancel_msg: str,
        confirm_msg: str,
        uow: AbstractUnitOfWork,
    ) -> m.MessageType:
        """
        Send a message with a confirmation request to the user.
        """
        pass

    @abstractmethod
    async def reply_edit_or_text(
        self, ref_message: m.MessageType, message_body: str, uow
    ) -> m.MessageType:
        pass

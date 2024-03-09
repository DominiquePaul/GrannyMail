from grannymail.services.unit_of_work import AbstractUnitOfWork
from grannymail.domain import models as m
from abc import ABC, abstractmethod
from typing import TypeVar, Generic

M = TypeVar("M", bound=m.Message)


class AbstractMessenger(ABC, Generic[M]):
    @abstractmethod
    async def reply_text(
        self, ref_message: M, message_body: str, uow: AbstractUnitOfWork
    ) -> M:
        """
        Send a text message to the recipient.
        """
        pass

    @abstractmethod
    async def reply_document(
        self,
        ref_message: M,
        file_data: bytes,
        filename: str,
        mime_type: str,
        uow: AbstractUnitOfWork,
    ) -> M:
        pass

    @abstractmethod
    async def reply_buttons(
        self,
        ref_message: M,
        main_msg: str,
        cancel_msg: str,
        confirm_msg: str,
        uow: AbstractUnitOfWork,
    ) -> M:
        """
        Send a message with a confirmation request to the user.
        """
        pass

    @abstractmethod
    async def reply_edit_or_text(self, ref_message: M, message_body: str, uow) -> M:
        pass

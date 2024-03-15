import json
import typing as t
import uuid

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, ApplicationBuilder
from telegram.ext._contexttypes import ContextTypes

import grannymail.config as cfg
import grannymail.constants as c
import grannymail.domain.models as m
from grannymail.services.unit_of_work import AbstractUnitOfWork
from grannymail.utils import message_utils, utils

from .base import AbstractMessenger


class Telegram(AbstractMessenger):
    def _build_application(self) -> Application:
        return ApplicationBuilder().token(cfg.BOT_TOKEN).build()

    def _get_message_type(self, update) -> tuple[c.types_message, str | None]:
        """
        Determines the type of message received in the update and extracts relevant information.

        This method checks the update object for various types of messages (e.g., voice, photo, document, text, or callback query)
        and returns a tuple containing the message type and, if applicable, the MIME type of the message content.

        Args:
            update (Update): The update object received from the Telegram API.

        Returns:
            tuple[str, str | None]: A tuple where the first element is a string representing the type of message
            ('voice', 'image', 'file', 'text', 'callback', or 'unknown') and the second element is either the MIME type
            of the message content (for 'voice', 'image', and 'file' types) or None.
        """
        if update.message is not None:
            message = update.message
            assert message is not None, "No message found"
            if message.voice:
                return "audio", message.voice.mime_type
            if message.photo:
                return "image", message.photo[-1].mime_type
            elif message.document:
                return "document", message.document.mime_type
            elif message.text:
                return "text", None
            else:
                return "unknown", None
        elif update.callback_query is not None:
            self.callback_query = update.callback_query
            return "interactive", None
        else:
            return "unknown", None

    async def _download_media(
        self, file_id: str, context: ContextTypes.DEFAULT_TYPE
    ) -> bytes:
        """
        Asynchronously downloads a file from Telegram servers using a file ID.

        This method retrieves the file associated with the given file ID from Telegram,
        then downloads the file content asynchronously using an HTTP GET request.

        Args:
            file_id (str): The unique identifier for the file to be downloaded.
            context (ContextTypes.DEFAULT_TYPE): The context from which the bot instance can be accessed.

        Returns:
            bytes: The content of the downloaded file as a bytes object.
        """
        file = await context.bot.getFile(file_id)
        async with httpx.AsyncClient() as client:
            response = await client.get(file.file_path)  # type: ignore
        return response.content

    # async def _download_media_old(
    #     self, update: Update, context: ContextTypes.DEFAULT_TYPE, media_type: str
    # ) -> list[bytes]:
    #     media_bytes_list = []
    #     assert update.message is not None, "No message found"
    #     if media_type == "image" and update.message.photo:
    #         for photo in update.message.photo:
    #             file_id = photo.file_id
    #             media_bytes = await self._download_media(file_id, context)
    #             media_bytes_list.append(media_bytes)
    #     return media_bytes_list

    async def process_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        uow: AbstractUnitOfWork,
    ) -> m.TelegramMessage:
        if not update.message and not update.callback_query:
            raise ValueError("No message or callback found")

        assert update.effective_user is not None
        assert update.effective_user.username is not None
        telegram_id: str = update.effective_user.username
        timestamp, message_id = self._extract_timestamp_and_id(update)

        user = self._get_or_create_user(uow, telegram_id, update, timestamp)

        message_type, attachment_mime_type = self._get_message_type(update)
        assert update.effective_chat, "No effective chat found"
        message = self._create_telegram_message_instance(
            user,
            telegram_id,
            timestamp,
            message_type,
            attachment_mime_type,
            update,
            message_id,  # todo this should be a unique value
        )

        if message_type == "interactive":
            assert (
                update.callback_query is not None
            ), "Message type is 'interactive' but no callback query found"
            message = await self._process_callback_query(update, message, uow)
        elif message_type == "text":
            message = self._process_text_message(update, message)
        elif message_type == "audio":
            message = await self._process_voice_message(update, message, context, uow)
        elif message_type in ["file", "image"]:
            # Placeholder for future file or image processing
            pass
        else:
            raise ValueError(f"Unhandled message type: '{message_type}'")

        return uow.tg_messages.add(message)

    def _extract_timestamp_and_id(self, update: Update) -> tuple[str, int]:
        """Extracts timestamp and message ID from the update."""
        if bool(update.message):
            return update.message.date.isoformat(), update.message.message_id
        elif bool(update.callback_query):
            assert update.callback_query.message is not None, "no message"
            return (
                update.callback_query.message.date.isoformat(),
                update.callback_query.message.message_id,
            )
        else:
            assert update.callback_query is not None
            assert update.callback_query.id is not None
            assert update.callback_query.message is not None
            return utils.get_utc_timestamp(), update.callback_query.message.id

    def _get_or_create_user(
        self, uow: AbstractUnitOfWork, telegram_id: str, update: Update, timestamp: str
    ) -> m.User:
        """Retrieves an existing user or creates a new one if not found."""
        user = uow.users.maybe_get_one(id=None, filters={"telegram_id": telegram_id})
        assert update.effective_user is not None
        if not user:
            user = m.User(
                user_id=str(uuid.uuid4()),
                created_at=timestamp,
                first_name=update.effective_user.first_name or "Unknown",
                last_name=update.effective_user.last_name or "Unknown",
                telegram_id=telegram_id,
            )
            uow.users.add(user)
        return user

    def _create_telegram_message_instance(
        self,
        user: m.User,
        telegram_id: str,
        timestamp: str,
        message_type: c.types_message,
        attachment_mime_type: str | None,
        update: Update,
        message_id: int,
    ) -> m.TelegramMessage:
        """Creates an instance of TelegramMessage."""
        assert update.effective_chat is not None
        return m.TelegramMessage(
            message_id=str(uuid.uuid4()),
            user_id=user.user_id,
            sent_by="user",
            timestamp=timestamp,
            attachment_mime_type=attachment_mime_type,
            message_type=message_type,
            tg_user_id=telegram_id,
            tg_chat_id=update.effective_chat.id,
            tg_message_id=f"{update.effective_chat.id}-{message_id}",
        )

    async def _process_callback_query(
        self, update: Update, message: m.TelegramMessage, uow: AbstractUnitOfWork
    ) -> m.TelegramMessage:
        """Processes the callback query."""
        assert update.callback_query is not None
        assert update.callback_query.data is not None
        await update.callback_query.answer()
        query_data = json.loads(update.callback_query.data)
        message_replied_to = uow.messages.get_one(query_data["mid"])
        if not message_replied_to:
            raise ValueError("Replied-to message not found")
        if not message_replied_to.command:
            raise ValueError("No command associated with replied-to message")
        message.response_to = query_data["mid"]
        message.action_confirmed = True if query_data["conf"] == "true" else False
        message.command = f"{message_replied_to.command}_callback"
        return message

    def _process_text_message(
        self, update: Update, message: m.TelegramMessage
    ) -> m.TelegramMessage:
        """Processes text messages."""
        assert update.message is not None
        assert update.message.text is not None
        message.command, message.message_body = message_utils.parse_command(
            update.message.text
        )
        return message

    async def _process_voice_message(
        self,
        update: Update,
        message: m.TelegramMessage,
        context: ContextTypes.DEFAULT_TYPE,
        uow: AbstractUnitOfWork,
    ) -> m.TelegramMessage:
        """Processes voice messages."""
        message.command = "voice"
        assert update.message is not None
        assert update.message.voice is not None
        voice_bytes = await self._download_media(update.message.voice.file_id, context)
        if update.message.voice.duration is None:
            raise ValueError("Voice message duration is None")
        message.memo_duration = update.message.voice.duration

        # Upload voice memo and add file record
        mime_type = "audio/ogg"
        path = uow.files_blob.upload(voice_bytes, message.user_id, mime_type)
        file_record = m.File(
            file_id=str(uuid.uuid4()),
            message_id=message.message_id,
            mime_type=mime_type,
            blob_path=path,
        )
        uow.files.add(file_record)
        return message

    async def reply_text(
        self, ref_message: m.TelegramMessage, message_body: str, uow: AbstractUnitOfWork
    ) -> m.TelegramMessage:
        r = await self._build_application().bot.sendMessage(
            chat_id=ref_message.tg_chat_id, text=message_body
        )

        response = m.TelegramMessage(
            message_id=str(uuid.uuid4()),
            timestamp=utils.get_utc_timestamp(),
            user_id=ref_message.user_id,
            sent_by="system",
            message_body=message_body,
            command=ref_message.command,
            draft_referenced=ref_message.draft_referenced,
            order_referenced=ref_message.order_referenced,
            message_type="text",
            phone_number=ref_message.phone_number,
            response_to=ref_message.message_id,
            tg_user_id=ref_message.tg_user_id,
            tg_chat_id=r.chat_id,
            tg_message_id=str(r.chat_id) + "-" + str(r.message_id),
        )
        return uow.tg_messages.add(response)

    async def reply_edit_or_text(
        self, ref_message: m.TelegramMessage, message_body: str, uow: AbstractUnitOfWork
    ) -> m.TelegramMessage:
        r = await self.callback_query.edit_message_text(text=message_body)
        response = m.TelegramMessage(
            message_id=str(uuid.uuid4()),
            timestamp=utils.get_utc_timestamp(),
            user_id=ref_message.user_id,
            message_type="text",
            sent_by="system",
            message_body=message_body,
            command=ref_message.command,
            draft_referenced=ref_message.draft_referenced,
            order_referenced=ref_message.order_referenced,
            phone_number=ref_message.phone_number,
            response_to=ref_message.message_id,
            tg_user_id=ref_message.tg_user_id,
            tg_chat_id=r.chat_id,
            tg_message_id=r.chat_id + "-" + str(r.message_id),
        )
        return uow.tg_messages.add(response)

    async def reply_document(
        self,
        ref_message: m.TelegramMessage,
        document_bytes: bytes,
        filename: str,
        mime_type: str,
        uow: AbstractUnitOfWork,
    ) -> m.TelegramMessage:
        r = await self._build_application().bot.sendDocument(
            chat_id=ref_message.tg_chat_id, document=document_bytes, filename=filename
        )
        response = m.TelegramMessage(
            message_id=str(uuid.uuid4()),
            timestamp=utils.get_utc_timestamp(),
            user_id=ref_message.user_id,
            sent_by="system",
            attachment_mime_type=mime_type,
            command=ref_message.command,
            draft_referenced=ref_message.draft_referenced,
            order_referenced=ref_message.order_referenced,
            message_type="document",
            phone_number=ref_message.phone_number,
            response_to=ref_message.message_id,
            tg_user_id=ref_message.tg_user_id,
            tg_chat_id=r.chat_id,
            tg_message_id=r.chat_id + "-" + str(r.message_id),
        )
        return uow.tg_messages.add(response)

    async def reply_buttons(
        self,
        ref_message: m.TelegramMessage,
        main_msg: str,
        cancel_msg: str,
        confirm_msg: str,
        uow: AbstractUnitOfWork,
    ) -> m.TelegramMessage:
        """
        Sends a message with a confirmation request to the user.

        This method sends a message to the user with two inline keyboard buttons for confirmation or cancellation.
        The buttons contain callback data with a reference message ID and the user's choice (True for confirm, False for cancel).

        Args:
            main_msg (str): The main message text to be sent to the user.
            cancel_msg (str): The text for the cancel button.
            confirm_msg (str): The text for the confirm button.
            reference_mid (str): The reference message ID to be included in the callback data.
        """
        assert ref_message.tg_chat_id is not None
        message_id = str(uuid.uuid4())
        # message_id = ref_message.message_id
        keyboard = [
            [
                InlineKeyboardButton(
                    confirm_msg,
                    callback_data=json.dumps({"mid": message_id, "conf": True}),
                ),
                InlineKeyboardButton(
                    cancel_msg,
                    callback_data=json.dumps({"mid": message_id, "conf": False}),
                ),
            ],
        ]

        # send message
        r = await self._build_application().bot.sendMessage(
            chat_id=ref_message.tg_chat_id,
            reply_markup=InlineKeyboardMarkup(keyboard),
            text=main_msg,
        )

        response = m.TelegramMessage(
            message_id=message_id,
            timestamp=utils.get_utc_timestamp(),
            user_id=ref_message.user_id,
            sent_by="system",
            message_body=main_msg,
            command=ref_message.command,
            draft_referenced=ref_message.draft_referenced,
            order_referenced=ref_message.order_referenced,
            message_type="interactive",
            phone_number=ref_message.phone_number,
            response_to=ref_message.message_id,
            tg_user_id=ref_message.tg_user_id,
            tg_chat_id=ref_message.tg_chat_id,
            tg_message_id=str(ref_message.tg_chat_id) + "-" + str(r.message_id),
        )
        return uow.tg_messages.add(response)

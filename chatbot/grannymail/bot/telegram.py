import json
import datetime
import httpx
from uuid import uuid4
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext._contexttypes import ContextTypes
from telegram.ext import ApplicationBuilder, Application


import grannymail.db.classes as dbc
from grannymail.utils import message_utils
import grannymail.config as cfg
import grannymail.db.repositories as repos

supaclient = repos.create_supabase_client()


class TelegramHandler:
    def _build_application(self) -> Application:
        return ApplicationBuilder().token(cfg.BOT_TOKEN).build()

    def _get_message_type(self, update) -> tuple[str, str | None]:
        if update.message is not None:
            message = update.message
            assert message is not None, "No message found"
            if message.voice:
                return "voice", message.voice.mime_type
            if message.photo:
                return "image", message.photo[-1].mime_type
            elif message.document:
                return "file", message.document.mime_type
            elif message.text:
                return "text", None
            else:
                return "unknown", None
        elif update.callback_query is not None:
            self.callback_query = update.callback_query
            return "callback", None
        else:
            return "unknown", None

    async def _download_file(
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

    async def _download_media(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, media_type: str
    ) -> list[bytes]:
        media_bytes_list = []
        assert update.message is not None, "No message found"
        if media_type == "image" and update.message.photo:
            for photo in update.message.photo:
                file_id = photo.file_id
                media_bytes = await self._download_file(file_id, context)
                media_bytes_list.append(media_bytes)
        return media_bytes_list

    async def parse_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> dbc.TelegramMessage:
        user_repo = repos.UserRepository(supaclient)
        message_repo = repos.TelegramMessagesRepository(supaclient)
        file_repo = repos.FileRepository(supaclient)
        sm_repo = repos.SystemMessageRepository(supaclient)
        blob_file_repo = repos.FilesBlobRepository(supaclient)

        if update.message is None and update.callback_query is None:
            raise ValueError("No message or callback found")

        telegram_id: str = update.effective_user.username  # type: ignore
        if update.message is not None:
            timestamp = str(update.message.date)
            message_id = update.message.message_id
        else:
            timestamp = str(datetime.datetime.now())
            message_id = update.callback_query.id  # type: ignore

        # Try to find user. Else create new user profile
        user = user_repo.maybe_get_one(id=None, filters={"telegram_id": telegram_id})
        if user is None:
            user = dbc.User(
                user_id=str(uuid4()),
                created_at=timestamp,
                first_name=update.effective_user.first_name
                if update.effective_user
                else "Unknown",
                last_name=update.effective_user.last_name
                if update.effective_user
                else "Unknown",
                telegram_id=telegram_id,
            )
            user_repo.add(user)

        message_type, attachment_mime_type = self._get_message_type(update)
        assert update.effective_chat is not None
        self.message = dbc.TelegramMessage(
            message_id=str(uuid4()),
            user_id=user.user_id,
            sent_by="user",
            timestamp=timestamp,
            attachment_mime_type=attachment_mime_type,
            message_type=message_type,
            tg_user_id=telegram_id,
            tg_chat_id=update.effective_chat.id,
            tg_message_id=(str(update.effective_chat.id) + "-" + str(message_id)),
        )

        # Handle callback query
        if update.callback_query is not None:
            # CallbackQueries need to be answered, even if no notification to the user is needed
            # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
            query = update.callback_query
            await query.answer()
            assert query.data is not None
            query_data = json.loads(query.data)

            message_replied_to = message_repo.get(query_data["mid"])

            if message_replied_to is None:
                raise ValueError("No message found")
            if message_replied_to.command is None:
                raise ValueError("No command association with message")
            self.message.response_to = query_data["mid"]
            self.message.action_confirmed = query_data["conf"]
            self.message.command = message_replied_to.command + "_callback"

        # Handle different message types
        if message_type == "text":
            (
                self.message.command,
                self.message.message_body,
            ) = message_utils.parse_command(
                update.message.text  # type: ignore
            )
        elif message_type == "voice":
            await self.send_message(sm_repo.get_msg("voice-confirm"))
            voice_bytes = await self._download_file(
                update.message.voice.file_id, context  # type: ignore
            )
            self.message.memo_duration = update.message.voice.duration  # type: ignore
            assert self.message.memo_duration is not None
            self.message.transcript = await message_utils.transcribe_voice_memo(
                voice_bytes, self.message.memo_duration
            )
            # 1. Upload voice memo to voice repository
            path = blob_file_repo.create_file_path(user.user_id)
            mime_type = "audio/ogg"
            blob_file_repo.upload(voice_bytes, path, mime_type)
            # 2. Add file to files repository
            file = dbc.File(
                file_id=str(uuid4()),
                message_id=self.message.message_id,
                mime_type=mime_type,
                blob_path=path,
            )
            file_repo.add(file)
        elif message_type == "file":
            # TODO: update message with any new data
            # Process file_bytes as needed
            # file_bytes = await self._download_file(
            #     update.message.document.file_id, context  # type: ignore
            # )
            pass
        elif message_type == "image":
            # TODO: update message with any new data
            # Process images_bytes_list as needed
            # images_bytes_list = await self._download_media(update, context, "image")
            pass
        else:
            raise ValueError(f"Unknown message type: '{message_type}'")

        return message_repo.add(self.message)

    async def send_message(self, message_body: str) -> dbc.TelegramMessage:
        message_repo = repos.TelegramMessagesRepository(supaclient)
        application = self._build_application()
        r = await application.bot.sendMessage(
            chat_id=self.message.tg_chat_id, text=message_body
        )

        response_message = dbc.TelegramMessage(
            message_id=str(uuid4()),
            timestamp=str(datetime.datetime.now()),
            user_id=self.message.user_id,
            sent_by="system",
            message_body=message_body,
            command=self.message.command,
            draft_referenced=self.message.draft_referenced,
            order_referenced=self.message.order_referenced,
            message_type="text",
            phone_number=self.message.phone_number,
            response_to=self.message.message_id,
            tg_user_id=self.message.tg_user_id,
            tg_chat_id=r.chat_id,
            tg_message_id=str(r.chat_id) + "-" + str(r.message_id),
        )
        return message_repo.add(response_message)

    async def edit_or_send_message(self, message_body: str) -> dbc.TelegramMessage:
        message_repo = repos.TelegramMessagesRepository(supaclient)
        r = await self.callback_query.edit_message_text(text=message_body)
        message = dbc.TelegramMessage(
            message_id=str(uuid4()),
            timestamp=str(datetime.datetime.now()),
            user_id=self.message.user_id,
            message_type="text",
            sent_by="system",
            message_body=message_body,
            command=self.message.command,
            draft_referenced=self.message.draft_referenced,
            order_referenced=self.message.order_referenced,
            phone_number=self.message.phone_number,
            response_to=self.message.message_id,
            tg_user_id=self.message.tg_user_id,
            tg_chat_id=r.chat_id,
            tg_message_id=r.chat_id + "-" + str(r.message_id),
        )
        return message_repo.add(message)

    async def send_document(
        self, document_bytes: bytes, filename: str, mime_type: str
    ) -> dbc.TelegramMessage:
        message_repo = repos.TelegramMessagesRepository(supaclient)
        application = self._build_application()
        r = await application.bot.sendDocument(
            chat_id=self.message.tg_chat_id, document=document_bytes, filename=filename
        )

        message = dbc.TelegramMessage(
            message_id=str(uuid4()),
            timestamp=str(datetime.datetime.now()),
            user_id=self.message.user_id,
            sent_by="system",
            attachment_mime_type=mime_type,
            command=self.message.command,
            draft_referenced=self.message.draft_referenced,
            order_referenced=self.message.order_referenced,
            message_type="document",
            phone_number=self.message.phone_number,
            response_to=self.message.message_id,
            tg_user_id=self.message.tg_user_id,
            tg_chat_id=r.chat_id,
            tg_message_id=r.chat_id + "-" + str(r.message_id),
        )
        return message_repo.add(message)

    async def send_message_confirmation_request(
        self, main_msg: str, cancel_msg: str, confirm_msg: str
    ) -> dbc.TelegramMessage:
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
        message_repo = repos.TelegramMessagesRepository(supaclient)
        message_id = str(uuid4())

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
        assert self.message.tg_chat_id is not None
        application = self._build_application()
        r = await application.bot.sendMessage(
            chat_id=self.message.tg_chat_id,
            reply_markup=InlineKeyboardMarkup(keyboard),
            text=main_msg,
        )

        return message_repo.add(
            dbc.TelegramMessage(
                message_id=message_id,
                timestamp=str(datetime.datetime.now()),
                user_id=self.message.user_id,
                sent_by="system",
                message_body=main_msg,
                command=self.message.command,
                draft_referenced=self.message.draft_referenced,
                order_referenced=self.message.order_referenced,
                message_type="interactive",
                phone_number=self.message.phone_number,
                response_to=self.message.message_id,
                tg_user_id=self.message.tg_user_id,
                tg_chat_id=self.message.tg_chat_id,
                tg_message_id=str(self.message.tg_chat_id) + "-" + str(r.message_id),
            )
        )

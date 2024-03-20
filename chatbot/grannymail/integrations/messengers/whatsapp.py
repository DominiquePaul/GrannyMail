import logging
import tempfile
import uuid
from datetime import datetime

import httpx
from fastapi import Request, Response
from pydantic import BaseModel
from tinytag import TinyTag  # mypy: ignore

import grannymail.config as cfg
import grannymail.domain.models as m
from grannymail.integrations.messengers.base import AbstractMessenger
from grannymail.services.unit_of_work import AbstractUnitOfWork
from grannymail.utils import message_utils, utils


class WebhookRequestData(BaseModel):
    object: str = ""
    entry: list = []


def fastapi_verify(request: Request):
    """
    On webook verification VERIFY_TOKEN has to match the token at the
    configuration and send back "hub.challenge" as success.
    """
    mode = request.query_params.get("hub.mode") == "subscribe"
    challenge = request.query_params.get("hub.challenge")
    token = request.query_params.get("hub.verify_token")

    if mode and challenge:
        if token != cfg.WHATSAPP_VERIFY_TOKEN:
            return Response(content="Verification token mismatch", status_code=403)
        return Response(content=request.query_params["hub.challenge"])

    return Response(content="Required arguments haven't passed.", status_code=400)


class Whatsapp(AbstractMessenger):
    def __init__(self):
        self.WHATSAPP_TOKEN = cfg.WHATSAPP_TOKEN
        self.WHATSAPP_API_VERSION = cfg.WHATSAPP_API_VERSION
        self.WHATSAPP_PHONE_NUMBER_ID = cfg.WHATSAPP_PHONE_NUMBER_ID
        self.WHATSAPP_VERIFY_TOKEN = cfg.WHATSAPP_VERIFY_TOKEN

    async def _post_httpx_request(
        self, url: str, data: dict | None = None, files: dict | None = None
    ) -> dict:
        """
        Send a POST request to the given URL with the provided data and files.

        This function constructs a POST request with the given data and files,
        sends the request to the given URL, and returns the JSON content of the response.
        If the response contains more than one contact or message, a ValueError is raised.

        Args:
            url (str): The URL to send the POST request to.
            data (dict, optional): The data to include in the request body. Defaults to None.
            files (dict, optional): The files to include in the request body. Defaults to None.

        Returns:
            dict: The JSON content of the response.
        """
        headers = {"Authorization": f"Bearer {cfg.WHATSAPP_TOKEN}"}
        if data:
            headers["Content-Type"] = "application/json"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=data, headers=headers, files=files)
            response.content
            response.raise_for_status()

        r = response.json()
        if data and (
            "contacts" in r
            and len(r["contacts"]) > 1
            or "messages" in r
            and len(r["messages"]) > 1
        ):
            raise ValueError(
                "Expected only one contact and one message in the response."
            )

        return r

    async def _download_media(self, media_id: str) -> bytes:
        """
        Download media from the given media_id.

        This function uses the media_id to construct a URL to the media file,
        sends a GET request to that URL, and returns the content of the response.
        If the media file cannot be found or accessed, an HTTP error is raised.

        Args:
            media_id (str): The ID of the media file to download.

        Returns:
            bytes: The content of the media file.
        """
        endpoint = f"https://graph.facebook.com/{self.WHATSAPP_API_VERSION}/{media_id}"
        headers = {"Authorization": f"Bearer {self.WHATSAPP_TOKEN}"}

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url=endpoint, headers=headers)
            response.raise_for_status()
            download_url = response.json()["url"]

            response = await client.get(download_url, headers=headers)
            response.raise_for_status()
            return response.content

    def _get_audio_duration(self, audio_bytes: bytes) -> float:
        """
        Get the duration of an audio file in seconds.

        This function uses the audio bytes and its mime type to determine the duration of the audio.
        Currently, it only supports audio files with the mime type 'audio/ogg'.

        Args:
            audio_bytes (bytes): The bytes of the audio file.
            mime_type (str): The MIME type of the audio file.

        Returns:
            int: The duration of the audio file in seconds. Returns 0 if the duration cannot be determined.
        """
        with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_file.flush()  # Ensure all data is written
            # Use TinyTag to read the duration of the audio file
            tag = TinyTag.get(tmp_file.name)
            return float(tag.duration) if tag.duration else 0

    async def _upload_media(
        self, file_data: bytes, file_name: str, mime_type: str
    ) -> dict:
        """
        Uploads a media file to the server.

        Args:
            file_data (bytes): The data of the file to be uploaded.
            file_name (str): The name of the file to be uploaded.
            mime_type (str): The MIME type of the file to be uploaded.

        Returns:
            dict: The JSON content of the response.
        """
        files: dict = {
            "file": (file_name, file_data, mime_type),
            "type": (None, "application/json"),
            "messaging_product": (None, "whatsapp"),
        }
        endpoint: str = f"https://graph.facebook.com/{self.WHATSAPP_API_VERSION}/{self.WHATSAPP_PHONE_NUMBER_ID}/media"
        return await self._post_httpx_request(url=endpoint, files=files)

    async def process_message(
        self, data: WebhookRequestData, uow: AbstractUnitOfWork
    ) -> m.WhatsappMessage:
        """
        Parses the incoming webhook request data to extract message details and constructs a WhatsappMessage object.

        This method handles the parsing of different types of messages received from WhatsApp, including
        text, audio, document, image, and interactive messages. It extracts the necessary information from the
        webhook data, such as the sender's phone number and the message timestamp. Depending on the message type,
        it delegates to specific methods for further processing.

        For media messages (audio, document, image), it calls `_process_media_message` to handle the attachment.
        For interactive messages, it calls `_process_interactive_message` to handle button replies.
        For text messages, it directly processes the message content.

        If the message type is unsupported, it raises a ValueError.

        Args:
            data (WebhookRequestData): The incoming webhook request data containing the message details.
            uow (AbstractUnitOfWork): A unit of work instance for database transactions.

        Returns:
            m.WhatsappMessage: The constructed message object ready to be persisted.

        Raises:
            ValueError: If the message type is unsupported.
        """
        webhook_id = data.entry[0]["id"]
        values = data.entry[0]["changes"][0]["value"]
        wa_message = values["messages"][0]
        phone_number = values["contacts"][0]["wa_id"]
        timestamp = utils.get_utc_timestamp()
        # datetime.utcfromtimestamp(int(wa_message["timestamp"])).isoformat()

        user = self._get_or_create_user(uow, phone_number, timestamp)
        message = self._create_message_object(
            webhook_id, values, wa_message, user, timestamp
        )

        # needs to be here to not violate foreign key relations for uploading files
        uow.wa_messages.add(message)

        if wa_message["type"] in ["audio", "document", "image"]:
            message = await self._process_media_message(wa_message, message, uow)
        elif wa_message["type"] == "interactive":
            message = self._process_interactive_message(wa_message, message, uow)
        elif wa_message["type"] == "text":
            message = self._process_text_message(wa_message, message)
        else:
            raise ValueError(f"Unsupported message type: '{wa_message['type']}'")

        return uow.wa_messages.update(message)

    def _get_or_create_user(
        self, uow: AbstractUnitOfWork, phone_number: str, timestamp: str
    ):
        """
        Retrieves an existing user based on the phone number or creates a new user if not found.

        Args:
            uow (AbstractUnitOfWork): A unit of work instance for database transactions.
            phone_number (str): The phone number of the user.
            timestamp (str): The timestamp when the user is created.

        Returns:
            User: The retrieved or newly created user object.
        """
        user = uow.users.maybe_get_one(id=None, filters={"phone_number": phone_number})
        if user is None:
            user = uow.users.add(
                m.User(
                    user_id=str(uuid.uuid4()),
                    created_at=timestamp,
                    phone_number=phone_number,
                )
            )
        return user

    def _create_message_object(self, webhook_id, values, wa_message, user, timestamp):
        """
        Creates a WhatsappMessage object from the webhook data.

        Args:
            values (dict): The values extracted from the webhook data.
            wa_message (dict): The WhatsApp message details extracted from the webhook data.
            user (User): The user object associated with the message.
            timestamp (str): The timestamp of the message.

        Returns:
            WhatsappMessage: The constructed WhatsappMessage object.
        """
        message = m.WhatsappMessage(
            message_id=str(uuid.uuid4()),
            user_id=user.user_id,
            sent_by="user",
            phone_number=values["contacts"][0]["wa_id"],
            timestamp=timestamp,
            message_type=wa_message["type"],
            wa_mid=wa_message["id"],
            # Corrected to use values instead of data
            wa_webhook_id=webhook_id,
            wa_phone_number_id=values["metadata"]["phone_number_id"],
            wa_profile_name=values["contacts"][0]["profile"]["name"],
        )
        context = wa_message.get("context")
        if context:
            message.wa_reference_wamid = context["id"]
            message.wa_reference_message_user_phone = context["from"]
        return message

    async def _process_media_message(
        self, wa_message: dict, message: m.WhatsappMessage, uow: AbstractUnitOfWork
    ) -> m.WhatsappMessage:
        """
        Processes media messages by setting the attachment MIME type and downloading the media.

        Args:
            wa_message (dict): The WhatsApp message details extracted from the webhook data.
            message (WhatsappMessage): The message object to update with media information.

        """
        message.attachment_mime_type = wa_message[message.message_type][
            "mime_type"
        ].split(";")[0]
        message.wa_media_id = wa_message[message.message_type]["id"]
        assert message.wa_media_id is not None
        media_bytes = await self._download_media(message.wa_media_id)

        if message.message_type == "audio":
            message.command = "voice"
            message.memo_duration = self._get_audio_duration(media_bytes)

        # Upload file bytes and add file record
        assert message.attachment_mime_type is not None
        path = uow.files_blob.upload(
            media_bytes, message.user_id, message.attachment_mime_type
        )
        file_record = m.File(
            file_id=str(uuid.uuid4()),
            message_id=message.message_id,
            mime_type=message.attachment_mime_type,
            blob_path=path,
        )
        uow.files.add(file_record)

        # return updates message object
        return message

    def _process_interactive_message(
        self, wa_message, message, uow
    ) -> m.WhatsappMessage:
        """
        Processes interactive messages, specifically button replies, and updates the message object accordingly.

        Args:
            wa_message (dict): The WhatsApp message details extracted from the webhook data.
            message (WhatsappMessage): The message object to update based on the interactive message.
            user (User): The user object associated with the message.
        """
        ref_msg_meaning = wa_message["interactive"]["button_reply"]["id"]
        if ref_msg_meaning not in ["true", "false"]:
            raise ValueError(
                f"ID of the response is not a boolean: '{ref_msg_meaning}'"
            )
        message.action_confirmed = True if ref_msg_meaning == "true" else False
        ref_message = uow.messages.maybe_get_one(
            id=None, filters={"wa_mid": message.wa_reference_wamid}
        )
        if ref_message:
            assert ref_message.command is not None
            message.command = ref_message.command + "_callback"
            message.response_to = ref_message.message_id
        else:
            error_msg = f"The incoming message referenced a message ID that could not be found:'{message.wa_reference_wamid}'"
            logging.error(error_msg)
            raise ValueError(error_msg)
        return message

    def _process_text_message(self, wa_message, message) -> m.WhatsappMessage:
        """
        Processes text messages by extracting the command and message body.

        Args:
            wa_message (dict): The WhatsApp message details extracted from the webhook data.
            message (WhatsappMessage): The message object to update with the text message content.
        """
        command, message_body = message_utils.parse_command(wa_message["text"]["body"])
        message.message_body = message_body
        message.command = command
        return message

    async def reply_text(
        self, ref_message: m.WhatsappMessage, message_body: str, uow: AbstractUnitOfWork
    ) -> m.WhatsappMessage:
        """
        Send a text message to the recipient.

        This function constructs a message with the given recipient_id and message,
        sends the message to the recipient, and returns the JSON content of the response.

        Args:
            recipient_id (str): The ID of the recipient to send the message to.
            message (str): The message to send.

        Returns:
            dict: The JSON content of the response.
        """
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": ref_message.phone_number,
            "type": "text",
            "text": {"preview_url": False, "body": message_body},
        }
        url = f"https://graph.facebook.com/{self.WHATSAPP_API_VERSION}/{self.WHATSAPP_PHONE_NUMBER_ID}/messages"
        r = await self._post_httpx_request(url=url, data=data)

        response = m.WhatsappMessage(
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
            wa_mid=r["messages"][0]["id"],
        )
        return uow.wa_messages.add(response)

    async def reply_document(
        self,
        ref_message: m.WhatsappMessage,
        file_data: bytes,
        filename: str,
        mime_type: str,
        uow: AbstractUnitOfWork,
    ) -> m.WhatsappMessage:
        """
        Sends a document to the specified recipient on WhatsApp.

        Args:
            recipient_id (str): The ID of the recipient to send the document to.
            file_data (bytes): The binary content of the document file.
            filename (str): The name of the document file.
            mime_type (str): The MIME type of the file, should be 'application/pdf'.

        Returns:
            dict: The JSON content of the response from the WhatsApp API.
        """
        media_id = (await self._upload_media(file_data, filename, mime_type))["id"]
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": ref_message.phone_number,
            "type": "document",
            "document": {"filename": filename, "id": media_id},
        }
        endpoint = f"https://graph.facebook.com/{self.WHATSAPP_API_VERSION}/{self.WHATSAPP_PHONE_NUMBER_ID}/messages"
        r = await self._post_httpx_request(url=endpoint, data=data)
        response = m.WhatsappMessage(
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
            wa_mid=r["messages"][0]["id"],
            wa_media_id=media_id,
        )
        return uow.wa_messages.add(response)

    async def reply_buttons(
        self,
        ref_message: m.WhatsappMessage,
        main_msg: str,
        cancel_msg: str,
        confirm_msg: str,
        uow: AbstractUnitOfWork,
    ) -> m.WhatsappMessage:
        """
        Send a quick reply message with buttons to the recipient.

        This function constructs a message with the given recipient_id and message,
        adds quick reply buttons, sends the message to the recipient, and returns
        the JSON content of the response.

        Args:
            recipient_id (str): The ID of the recipient to send the message to.
            message (str): The message to send.
            buttons (list[str]): A list of button titles for quick replies.

        Returns:
            dict: The JSON content of the response.
        """
        btns = [
            {"type": "reply", "reply": {"id": "false", "title": cancel_msg}},
            {"type": "reply", "reply": {"id": "true", "title": confirm_msg}},
        ]
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": ref_message.phone_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": main_msg},
                "action": {"buttons": btns},
            },
        }
        endpoint = f"https://graph.facebook.com/{self.WHATSAPP_API_VERSION}/{self.WHATSAPP_PHONE_NUMBER_ID}/messages"
        r = await self._post_httpx_request(url=endpoint, data=data)

        response = m.WhatsappMessage(
            message_id=str(uuid.uuid4()),
            timestamp=utils.get_utc_timestamp(),
            user_id=ref_message.user_id,
            sent_by="system",
            message_body=main_msg,
            command=ref_message.command,
            draft_referenced=ref_message.draft_referenced,
            order_referenced=ref_message.order_referenced,
            message_type="text",
            phone_number=ref_message.phone_number,
            response_to=ref_message.message_id,
            wa_mid=r["messages"][0]["id"],
        )
        return uow.wa_messages.add(response)

    async def reply_edit_or_text(
        self, ref_message: m.WhatsappMessage, message_body: str, uow
    ) -> m.WhatsappMessage:
        return await self.reply_text(
            ref_message=ref_message, message_body=message_body, uow=uow
        )

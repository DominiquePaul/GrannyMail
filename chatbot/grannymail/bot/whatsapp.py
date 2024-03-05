from uuid import uuid4
import logging
import tempfile
from datetime import datetime

import httpx
from fastapi import Request, Response
from pydantic import BaseModel
from tinytag import TinyTag  # mypy: ignore

import grannymail.config as cfg
import grannymail.db.classes as dbc
from grannymail.utils import message_utils
import grannymail.db.repositories as repos

supaclient = repos.create_supabase_client()


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


class WhatsappHandler:
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
            response = await client.get(endpoint, headers=headers)
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
        # Using TinyTag to read the duration of an audio file

        with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_file.flush()  # Ensure all data is written
            # Use TinyTag to read the duration of the audio file
            tag = TinyTag.get(tmp_file.name)
            return float(tag.duration) if tag.duration else 0

    async def parse_message(self, data: WebhookRequestData):
        """Parses the incoming webhook request and returns a message object

        Args:
            data (WebhookRequestData): _description_

        Raises:
            ValueError: _description_
            ValueError: _description_

        Returns:
            message: dbc.Message

        Also does:
        - Creates a user if the user does not exist
        - Sends a confirmation message if the message is a voice message
        - Adds message to database
        - Downloads any given file and uploads it to file storage

        # Alternative flow in service (?) layer:
        # - Parse the message
        # - Send a confirmation message if the message is a voice message (needs to happen asap)
        # - Optionally create user if none found
        # - Optionally download file if message is an image or voice memo
        # - Add the message to the database
        """
        user_repo = repos.UserRepository(supaclient)
        message_repo = repos.WhatsappMessagesRepository(supaclient)
        file_repo = repos.FileRepository(supaclient)
        blob_file_repo = repos.FilesBlobRepository(supaclient)

        values = data.entry[0]["changes"][0]["value"]
        wa_message = values["messages"][0]
        phone_number = values["contacts"][0]["wa_id"]

        timestamp = datetime.utcfromtimestamp(int(wa_message["timestamp"])).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )

        # Get or create user
        user = user_repo.get(id=None, filters={"phone_number": phone_number})
        if user is None:
            user = user_repo.add(
                dbc.User(
                    user_id=str(uuid4()),
                    created_at=timestamp,
                    phone_number=phone_number,
                )
            )
        self.message = dbc.WhatsappMessage(
            message_id=str(uuid4()),
            user_id=user.user_id,
            sent_by="user",
            phone_number=values["contacts"][0]["wa_id"],
            timestamp=timestamp,
            message_type=wa_message["type"],
            wa_mid=wa_message["id"],
            wa_webhook_id=data.entry[0]["id"],
            wa_phone_number_id=values["metadata"]["phone_number_id"],
            wa_profile_name=values["contacts"][0]["profile"]["name"],
        )

        # Initialize media_bytes to None to ensure it's always defined
        media_bytes = None

        context = wa_message.get("context")
        if context:
            self.message.wa_reference_wamid = context["id"]
            self.message.wa_reference_message_user_phone = context["from"]

        # Process message based on type
        if wa_message["type"] == "text":
            command, message_body = message_utils.parse_command(
                wa_message["text"]["body"]
            )
            self.message.message_body = message_body
            self.message.command = command
        elif wa_message["type"] in ["audio", "document", "image"]:
            media_type = wa_message["type"]
            if media_type == "audio":
                # notify user that memo was received
                sm_rep = repos.SystemMessageRepository(supaclient)
                await self.send_message(sm_rep.get_msg("voice-confirm"))
                self.message.command = "voice"
            self.message.attachment_mime_type = wa_message[media_type][
                "mime_type"
            ].split(";")[0]
            self.message.wa_media_id = wa_message[media_type]["id"]
            assert self.message.wa_media_id is not None
            media_bytes = await self._download_media(self.message.wa_media_id)
            if wa_message["type"] == "audio":
                duration = self._get_audio_duration(media_bytes)
                self.message.memo_duration = duration
                self.message.transcript = await message_utils.transcribe_voice_memo(
                    media_bytes, duration=duration
                )
                # 1. Upload voice memo to voice repository
                path = blob_file_repo.create_file_path(user.user_id)
                mime_type = "audio/ogg"
                blob_file_repo.upload(media_bytes, path, mime_type)
                # 2. Add file to files repository
                file_repo.add(
                    dbc.File(
                        file_id=str(uuid4()),
                        message_id=self.message.message_id,
                        mime_type=mime_type,
                        blob_path=path,
                    )
                )
        elif wa_message["type"] == "interactive":
            ref_msg_meaning = wa_message["interactive"]["button_reply"]["id"]
            if ref_msg_meaning not in ["true", "false"]:
                raise ValueError(
                    f"ID of the response is not a boolean: '{ref_msg_meaning}'"
                )
            self.message.action_confirmed = True if ref_msg_meaning == "true" else False

            # We want to get the content of the message referenced to understand what kind of callback this is
            ref_message = message_repo.maybe_get_one(
                id=None, filters={"wa_mid": self.message.wa_reference_wamid}
            )
            if ref_message is None:
                logging.info(
                    f"The interactive message referenced the following message ID which could not be found however:'{self.message.wa_reference_wamid}'"
                )
            else:
                assert ref_message.command is not None
                self.message.command = ref_message.command + "_callback"
                self.message.response_to = ref_message.message_id
        else:
            raise ValueError(f"Unsupported message type: '{wa_message['type']}'")

        # Create and add message to database
        return message_repo.add(self.message)

    async def send_message(self, message_body: str) -> dbc.WhatsappMessage:
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
        message_repo = repos.WhatsappMessagesRepository(supaclient)
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self.message.phone_number,
            "type": "text",
            "text": {"preview_url": False, "body": message_body},
        }
        url = f"https://graph.facebook.com/{self.WHATSAPP_API_VERSION}/{self.WHATSAPP_PHONE_NUMBER_ID}/messages"
        r = await self._post_httpx_request(url, data=data)

        message = dbc.WhatsappMessage(
            message_id=str(uuid4()),
            timestamp=str(datetime.utcnow()),
            user_id=self.message.user_id,
            sent_by="system",
            message_body=message_body,
            command=self.message.command,
            draft_referenced=self.message.draft_referenced,
            order_referenced=self.message.order_referenced,
            message_type="text",
            phone_number=self.message.phone_number,
            response_to=self.message.message_id,
            wa_mid=r["messages"][0]["id"],
        )
        return message_repo.add(message)

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
        return await self._post_httpx_request(endpoint, files=files)

    async def send_document(
        self, file_data: bytes, filename: str, mime_type: str
    ) -> dbc.Message:
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
        message_repo = repos.WhatsappMessagesRepository(supaclient)
        media_id = (await self._upload_media(file_data, filename, mime_type))["id"]
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self.message.phone_number,
            "type": "document",
            "document": {"filename": filename, "id": media_id},
        }
        endpoint = f"https://graph.facebook.com/{self.WHATSAPP_API_VERSION}/{self.WHATSAPP_PHONE_NUMBER_ID}/messages"
        r = await self._post_httpx_request(endpoint, data=data)
        return message_repo.add(
            dbc.WhatsappMessage(
                message_id=str(uuid4()),
                timestamp=str(datetime.utcnow()),
                user_id=self.message.user_id,
                sent_by="system",
                attachment_mime_type=mime_type,
                command=self.message.command,
                draft_referenced=self.message.draft_referenced,
                order_referenced=self.message.order_referenced,
                message_type="document",
                phone_number=self.message.phone_number,
                response_to=self.message.message_id,
                wa_mid=r["messages"][0]["id"],
                wa_media_id=media_id,
            )
        )

    async def send_message_confirmation_request(
        self, main_msg: str, cancel_msg: str, confirm_msg: str
    ) -> dbc.Message:
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
        message_repo = repos.WhatsappMessagesRepository(supaclient)
        btns = [
            {"type": "reply", "reply": {"id": "false", "title": cancel_msg}},
            {"type": "reply", "reply": {"id": "true", "title": confirm_msg}},
        ]
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self.message.phone_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": main_msg},
                "action": {"buttons": btns},
            },
        }
        endpoint = f"https://graph.facebook.com/{self.WHATSAPP_API_VERSION}/{self.WHATSAPP_PHONE_NUMBER_ID}/messages"
        r = await self._post_httpx_request(endpoint, data=data)

        return message_repo.add(
            dbc.WhatsappMessage(
                message_id=str(uuid4()),
                timestamp=str(datetime.utcnow()),
                user_id=self.message.user_id,
                sent_by="system",
                message_body=main_msg,
                command=self.message.command,
                draft_referenced=self.message.draft_referenced,
                order_referenced=self.message.order_referenced,
                message_type="text",
                phone_number=self.message.phone_number,
                response_to=self.message.message_id,
                wa_mid=r["messages"][0]["id"],
            )
        )

    async def edit_or_send_message(self, message_body: str) -> dbc.WhatsappMessage:
        return await self.send_message(message_body)

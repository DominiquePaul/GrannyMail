import logging
import tempfile
import io
from datetime import datetime

import httpx
from fastapi import Request, Response
from pydantic import BaseModel
from tinytag import TinyTag  # mypy: ignore

import grannymail.config as cfg
import grannymail.db.classes as dbc
import grannymail.db.supaclient as supaclient
from grannymail.utils import message_utils
import grannymail.utils.message_utils as msg_utils

db_client = supaclient.SupabaseClient()


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
    def __init__(self, data: WebhookRequestData):
        self.data = data

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

    async def parse_message(self):
        values = self.data.entry[0]["changes"][0]["value"]
        wa_message = values["messages"][0]
        user = db_client.get_or_create_user(
            dbc.User(phone_number=values["contacts"][0]["wa_id"])
        )
        message_data = {
            "user_id": user.user_id,
            "sent_by": "user",
            "phone_number": values["contacts"][0]["wa_id"],
            "timestamp": datetime.utcfromtimestamp(
                int(wa_message["timestamp"])
            ).strftime("%Y-%m-%d %H:%M:%S.%f"),
            "message_type": wa_message["type"],
            "wa_mid": wa_message["id"],
            "wa_webhook_id": self.data.entry[0]["id"],
            "wa_phone_number_id": values["metadata"]["phone_number_id"],
            "wa_profile_name": values["contacts"][0]["profile"]["name"],
        }

        # Initialize media_bytes to None to ensure it's always defined
        media_bytes = None

        context = wa_message.get("context")
        if context:
            message_data.update(
                {
                    "wa_reference_wamid": context["id"],
                    "wa_reference_message_user_phone": context["from"],
                }
            )

        # Process message based on type
        if wa_message["type"] == "text":
            command, message_body = message_utils.parse_command(
                wa_message["text"]["body"]
            )
            message_data.update({"message_body": message_body, "command": command})
        elif wa_message["type"] in ["audio", "document", "image"]:
            media_type = wa_message["type"]
            if media_type == "audio":
                # notify user that memo was received
                self.message = dbc.WhatsappMessage(**message_data)
                await self.send_message(db_client.get_system_message("voice-confirm"))
                message_data.update({"command": "voice"})
            message_data.update(
                {
                    "attachment_mime_type": wa_message[media_type]["mime_type"].split(
                        ";"
                    )[0],
                    "wa_media_id": wa_message[media_type]["id"],
                }
            )
            media_bytes = await self._download_media(message_data["wa_media_id"])
            if wa_message["type"] == "audio":
                duration = self._get_audio_duration(media_bytes)
                message_data.update(
                    {
                        "memo_duration": duration,
                        "transcript": await message_utils.transcribe_voice_memo(
                            media_bytes, duration=duration
                        ),
                    }
                )
        elif wa_message["type"] == "interactive":
            message_referenced_meaning = wa_message["interactive"]["button_reply"]["id"]
            if message_referenced_meaning == "true":
                message_data.update({"action_confirmed": True})
            elif message_referenced_meaning == "false":
                message_data.update({"action_confirmed": False})
            else:
                raise ValueError(
                    f"ID of the response is not a boolean: '{message_referenced_meaning}"
                )

            # We want to get the content of the message referenced to understand what kind of callback this is
            ref_message = db_client.get_message(
                dbc.WhatsappMessage(wa_mid=message_data["wa_reference_wamid"])
            )
            if ref_message is None:
                logging.info(
                    f"The interactive message referenced the following message ID which could not be found however:'{message_data['wa_reference_wamid']}'"
                )
            else:
                assert ref_message.command is not None
                message_data.update(
                    {
                        "command": ref_message.command + "_callback",
                        "response_to": ref_message.message_id,
                    }
                )
        else:
            raise ValueError(f"Unsupported message type: '{wa_message['type']}'")

        # Create and add message to database
        message = dbc.WhatsappMessage(**message_data)
        message = db_client.add_message(message)

        # Special handling for voice messages
        if message_data["message_type"] == "audio" and media_bytes is not None:
            db_client.register_voice_message(media_bytes, message)

        self.message = message

    async def send_message(self, message_body: str):
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
            "to": self.message.phone_number,
            "type": "text",
            "text": {"preview_url": False, "body": message_body},
        }
        url = f"https://graph.facebook.com/{self.WHATSAPP_API_VERSION}/{self.WHATSAPP_PHONE_NUMBER_ID}/messages"
        r = await self._post_httpx_request(url, data=data)

        system_message = db_client.add_message(
            dbc.WhatsappMessage(
                user_id=self.message.user_id,
                sent_by="system",
                message_body=message_body,
                command=self.message.command,
                draft_referenced=self.message.draft_referenced,
                message_type="text",
                phone_number=self.message.phone_number,
                response_to=self.message.message_id,
                wa_mid=r["messages"][0]["id"],
            )
        )

        return r

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
    ) -> dict:
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
            "to": self.message.phone_number,
            "type": "document",
            "document": {"filename": filename, "id": media_id},
        }
        endpoint = f"https://graph.facebook.com/{self.WHATSAPP_API_VERSION}/{self.WHATSAPP_PHONE_NUMBER_ID}/messages"
        r = await self._post_httpx_request(endpoint, data=data)
        db_client.add_message(
            dbc.WhatsappMessage(
                user_id=self.message.user_id,
                sent_by="system",
                attachment_mime_type=mime_type,
                command=self.message.command,
                draft_referenced=self.message.draft_referenced,
                message_type="document",
                phone_number=self.message.phone_number,
                response_to=self.message.message_id,
                wa_mid=r["messages"][0]["id"],
                wa_media_id=media_id,
            )
        )
        return r

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

        system_message = db_client.add_message(
            dbc.WhatsappMessage(
                user_id=self.message.user_id,
                sent_by="system",
                message_body=main_msg,
                command=self.message.command,
                draft_referenced=self.message.draft_referenced,
                message_type="text",
                phone_number=self.message.phone_number,
                response_to=self.message.message_id,
                wa_mid=r["messages"][0]["id"],
            )
        )

        return system_message

    async def edit_or_send_message(self, message_body: str):
        await self.send_message(message_body)


# async def process_webhook_data(data: WebhookRequestData) -> WamBase | None:
#     if data.entry[0].get("changes", [{}])[0].get("value", {}).get("statuses"):
#         logging.info("Received a WhatsApp status update.")
#         return None
#     # if not a status update
#     try:
#         if is_valid_whatsapp_message(data):
#             wam = await parse_whatsapp_message(data)
#             return wam
#         else:
#             # if the request is not a WhatsApp API event, return an error
#             raise HTTPException(status_code=404, detail="Not a WhatsApp API event")
#     except json.JSONDecodeError:
#         logging.error("Failed to decode JSON")
#         raise HTTPException(status_code=400, detail="Invalid JSON provided")


# def is_valid_whatsapp_message(body: WebhookRequestData) -> bool:
#     """
#     Validates the structure of the incoming webhook event to ensure it contains a WhatsApp message.

#     Args:
#         body (WebhookRequestData): The incoming webhook request data.

#     Returns:
#         bool: True if the message structure is valid, False otherwise.
#     """
#     try:
#         return bool(body.entry[0]["changes"][0]["value"]["messages"][0])
#     except (IndexError, KeyError):
#         return False


# async def parse_whatsapp_message(body: WebhookRequestData) -> WamBase:
#     """
#     Parse the incoming webhook request data and return an instance of WamBase or WamMediaType.

#     This function extracts the necessary information from the webhook request data to
#     instantiate and return a WamBase dataclass object for text messages or a WamMediaType
#     dataclass object for media messages (audio, document, image). If the message type is
#     unsupported, it raises a ValueError.

#     Args:
#         body (WebhookRequestData): The incoming webhook request data.

#     Returns:
#         WamBase: An instance of WamBase for text messages.
#         WamMediaType: An instance of WamMediaType for media messages.
#     """
#     values = body.entry[0]["changes"][0]["value"]
#     message = values["messages"][0]
#     wam_data = {
#         "webhook_id": body.entry[0]["id"],
#         "wamid": message["id"],
#         "wa_phone_number_id": values["metadata"]["phone_number_id"],
#         "phone_number": values["contacts"][0]["wa_id"],
#         "profile_name": values["contacts"][0]["profile"]["name"],
#         "message_type": message["type"],
#         "timestamp": message["timestamp"],
#     }

#     if message.get("context"):
#         wam_data.update(
#             {
#                 "reference_wamid": message["context"]["id"],
#                 "reference_message_user_phone": message["context"]["from"],
#             }
#         )
#     if message["type"] == "text":
#         wam_data["message_body"] = message["text"]["body"]
#     elif message["type"] in ["audio", "document", "image"]:
#         wam_data.update(
#             {
#                 "mime_type": message[message["type"]]["mime_type"],
#                 "media_id": message[message["type"]]["id"],
#             }
#         )
#         wam_media = WamMediaType(**wam_data)
#         wam_media.media_bytes = await _download_media(wam_media.media_id)
#         return wam_media
#     else:
#         raise ValueError(f"Unsupported message type: '{message['type']}'")

#     return WamBase(**wam_data)


# async def send_message(recipient_id: str, message: str) -> dict:
#     """
#     Send a text message to the recipient.

#     This function constructs a message with the given recipient_id and message,
#     sends the message to the recipient, and returns the JSON content of the response.

#     Args:
#         recipient_id (str): The ID of the recipient to send the message to.
#         message (str): The message to send.

#     Returns:
#         dict: The JSON content of the response.
#     """
#     data = {
#         "messaging_product": "whatsapp",
#         "recipient_type": "individual",
#         "to": recipient_id,
#         "type": "text",
#         "text": {"preview_url": False, "body": message},
#     }
#     url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
#     return await _post_httpx_request(url, data=data)


# async def send_quick_reply_message(
#     recipient_id: str, message: str, buttons: list[str]
# ) -> dict:
#     """
#     Send a quick reply message with buttons to the recipient.

#     This function constructs a message with the given recipient_id and message,
#     adds quick reply buttons, sends the message to the recipient, and returns
#     the JSON content of the response.

#     Args:
#         recipient_id (str): The ID of the recipient to send the message to.
#         message (str): The message to send.
#         buttons (list[str]): A list of button titles for quick replies.

#     Returns:
#         dict: The JSON content of the response.
#     """
#     btns = [
#         {"type": "reply", "reply": {"id": f"choice{idx+1}", "title": b}}
#         for idx, b in enumerate(buttons)
#     ]
#     data = {
#         "messaging_product": "whatsapp",
#         "recipient_type": "individual",
#         "to": recipient_id,
#         "type": "interactive",
#         "interactive": {
#             "type": "button",
#             "body": {"text": message},
#             "action": {"buttons": btns},
#         },
#     }
#     endpoint = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
#     return await _post_httpx_request(endpoint, data=data)


# async def send_pdf(
#     recipient_id: str, file_data: bytes, file_name: str, mime_type: str
# ) -> dict:
#     """
#     Sends a PDF file to the specified recipient on WhatsApp.

#     Args:
#         recipient_id (str): The ID of the recipient to send the PDF to.
#         file_data (bytes): The binary content of the PDF file.
#         file_name (str): The name of the PDF file.
#         mime_type (str): The MIME type of the file, should be 'application/pdf'.

#     Returns:
#         dict: The JSON content of the response from the WhatsApp API.
#     """
#     media_id = (await _upload_media(file_data, file_name, mime_type))["id"]
#     data = {
#         "messaging_product": "whatsapp",
#         "recipient_type": "individual",
#         "to": recipient_id,
#         "type": "document",
#         "document": {"filename": file_name, "id": media_id},
#     }
#     endpoint = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
#     return await _post_httpx_request(endpoint, data=data)

from unittest.mock import AsyncMock, Mock, patch

import pytest

import grannymail.domain.models as m
from grannymail.integrations.messengers.whatsapp import Whatsapp
from grannymail.utils import utils
from tests import utils as test_utils


class TestWhatsappMessenger:
    def test_get_audio_duration(self):
        # use local audio file
        whatsapp = Whatsapp()
        with open("tests/test_data/example_voice_memo.ogg", "rb") as f:
            mybytes = f.read()
        duration = whatsapp._get_audio_duration(mybytes)
        assert duration == 14.6395

    @pytest.mark.asyncio
    @patch(
        "grannymail.utils.utils.get_utc_timestamp",
        return_value="2024-01-26T17:17:17.123+00:00",
    )
    @patch("uuid.uuid4", new_callable=Mock)
    async def test_process_message_text(self, mock_uuid4, mock_get_utc_ts, fake_uow):
        # create whatsapp message and manually compare output
        mock_uuid4.return_value = "00000000-0000-0000-0000-000000000000"
        whatsapp = Whatsapp()
        wamid = "wamid.12345"
        data = test_utils._create_whatsapp_text_message("/send  Doris ", wamid)
        with fake_uow:
            message = await whatsapp.process_message(data, fake_uow)
        expected_message = m.WhatsappMessage(
            message_id="00000000-0000-0000-0000-000000000000",
            user_id="00000000-0000-0000-0000-000000000000",
            messaging_platform="WhatsApp",
            command="send",
            timestamp="2024-01-26T17:17:17.123+00:00",
            sent_by="user",
            message_type="text",
            message_body="Doris",
            phone_number="491515222222",
            wa_mid=wamid,
            wa_webhook_id="206144975918077",
            wa_phone_number_id="196914110180497",
            wa_profile_name="Mike Mockowitz",
        )
        assert message == expected_message

    @pytest.mark.asyncio
    @patch(
        "grannymail.utils.utils.get_utc_timestamp",
        return_value="2024-01-26T17:17:17.123+00:00",
    )
    @patch("uuid.uuid4", new_callable=Mock)
    async def test_process_message_interactive(
        self, mock_uuid4, mock_get_utc_ts, fake_uow, wa_message, user
    ):
        # setup
        # create /send message and add it to db
        wa_message.message_body = "/send Doris"
        with fake_uow:
            fake_uow.users.add(user)
            fake_uow.wa_messages.add(wa_message)
        # create a callback message
        data_callback = test_utils.create_whatsapp_callback_message(
            wa_message.wa_mid, "true"
        )

        # create whatsapp message and manually compare output
        mock_uuid4.return_value = "00000000-0000-0000-0000-000000000000"
        whatsapp = Whatsapp()
        with fake_uow:
            message = await whatsapp.process_message(data_callback, fake_uow)
        expected_message = m.WhatsappMessage(
            message_id="00000000-0000-0000-0000-000000000000",
            user_id=user.user_id,
            messaging_platform="WhatsApp",
            command="send_callback",
            timestamp="2024-01-26T17:17:17.123+00:00",
            sent_by="user",
            message_type="interactive",
            message_body=None,
            phone_number="491515222222",
            wa_mid="wamid.HBgNNDkxNTE1OTkyNjE2MhUCABIYFDNBQzk0NUREMERBQkVEMDI3MUZBAA==",
            wa_webhook_id="206144975918077",
            wa_phone_number_id="196914110180497",
            wa_profile_name="Mike Mockowitz",
            action_confirmed=True,
            response_to=wa_message.message_id,
            wa_reference_wamid=wa_message.wa_mid,
            wa_reference_message_user_phone=wa_message.phone_number,
        )
        assert message == expected_message

    @pytest.mark.asyncio
    @patch(
        "grannymail.utils.utils.get_utc_timestamp",
        return_value="2024-01-26T17:17:17.123+00:00",
    )
    @patch(
        "grannymail.integrations.messengers.whatsapp.Whatsapp._download_media",
        new_callable=AsyncMock,
    )
    @patch("uuid.uuid4", new_callable=Mock)
    async def test_process_message_media(
        self, mock_uuid4, mock_download_media, mock_get_utc_ts, fake_uow
    ):
        # setup
        with open("tests/test_data/example_voice_memo.ogg", "rb") as f:
            mock_download_media.return_value = f.read()
        mock_uuid4.return_value = "00000000-0000-0000-0000-000000000000"

        # call
        whatsapp = Whatsapp()
        wa_voice_memo = test_utils._create_wa_voice_memo_msg()
        with fake_uow:
            message = await whatsapp.process_message(wa_voice_memo, fake_uow)

        # tests
        expected_message = m.WhatsappMessage(
            message_id="00000000-0000-0000-0000-000000000000",
            user_id="00000000-0000-0000-0000-000000000000",
            messaging_platform="WhatsApp",
            command="voice",
            attachment_mime_type="audio/ogg",
            timestamp="2024-01-26T17:17:17.123+00:00",
            sent_by="user",
            message_type="audio",
            message_body=None,
            phone_number="491515222222",
            wa_mid="wamid.HBgNNDkxNTE1OTkyNjE2MhUCABIYFDNBM0M2MDQ3OEI4RDcxMDMwODE0AA==",
            wa_media_id="1048715742889904",
            wa_webhook_id="206144975918077",
            wa_phone_number_id="196914110180497",
            wa_profile_name="Mike Mockowitz",
            memo_duration=14.6395,
        )
        # check for media in fake_uow
        assert message == expected_message

    def test_get_or_create_user__get(self, fake_uow, user):
        whatsapp = Whatsapp()
        timestamp = utils.get_utc_timestamp()
        with fake_uow:
            fake_uow.users.add(user)
            user_returned = whatsapp._get_or_create_user(
                fake_uow, user.phone_number, timestamp
            )
        assert user == user_returned

    def test_get_or_create_user__create(self, fake_uow):
        whatsapp = Whatsapp()
        timestamp = utils.get_utc_timestamp()
        with fake_uow:
            user_returned = whatsapp._get_or_create_user(
                fake_uow, "44131231231", timestamp
            )
            assert isinstance(user_returned, m.User)
            assert user_returned.created_at == timestamp
            assert fake_uow.users.get_one(user_returned.user_id) == user_returned

    # this test could be more elaborate but its hard to test without sending something to the real API
    @pytest.mark.asyncio
    @patch(
        "grannymail.integrations.messengers.whatsapp.Whatsapp._post_httpx_request",
        new_callable=AsyncMock,
    )
    async def test_reply_text(self, mock_post_httpx, fake_uow, user, wa_message):
        mock_post_httpx.return_value = {"messages": [{"id": "some_message_id"}]}

        with fake_uow:
            fake_uow.users.add(user)
            fake_uow.wa_messages.add(wa_message)
            msg_sent = await Whatsapp().reply_text(wa_message, "hey", fake_uow)
        assert isinstance(msg_sent, m.WhatsappMessage)

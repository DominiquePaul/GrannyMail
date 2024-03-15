from unittest.mock import AsyncMock, Mock, patch

import pytest

import grannymail.domain.models as m
import tests.utils as utils
from grannymail.integrations.messengers.telegram import Telegram


class TestTelegramMessenger:
    @pytest.mark.asyncio
    @patch("uuid.uuid4", new_callable=Mock)
    async def test_process_message_text(self, mock_uuid4, fake_uow):
        # setup
        mock_uuid4.return_value = "00000000-0000-0000-0000-000000000000"
        update, context = utils._create_telegram_text_message_objects("/send  Doris  ")

        # call
        message = await Telegram().process_message(update, context, fake_uow)

        # test
        expected_message = m.TelegramMessage(
            message_id="00000000-0000-0000-0000-000000000000",
            user_id="00000000-0000-0000-0000-000000000000",
            messaging_platform="Telegram",
            command="send",
            timestamp="2024-01-26T23:42:09+00:00",
            sent_by="user",
            message_type="text",
            message_body="Doris",
            tg_user_id="mike_mockowitz",
            tg_chat_id=1234,
            tg_message_id="1234-6969",
        )
        assert message == expected_message

    @pytest.mark.asyncio
    @patch("telegram._callbackquery.CallbackQuery.answer", new_callable=AsyncMock)
    @patch("uuid.uuid4", new_callable=Mock)
    async def test_process_message_interactive(
        self, mock_uuid4, mock_answer, fake_uow, tg_message
    ):
        # setup
        tg_message.message_body = "/send Doris"
        fake_uow.tg_messages.add(tg_message)

        mock_uuid4.return_value = "00000000-0000-0000-0000-000000000000"
        update, context = utils.create_telegram_callback_message(
            tg_message.message_id, "true"
        )

        # call
        message = await Telegram().process_message(update, context, fake_uow)

        # test
        expected_message = m.TelegramMessage(
            message_id="00000000-0000-0000-0000-000000000000",
            user_id="00000000-0000-0000-0000-000000000000",
            messaging_platform="Telegram",
            timestamp="2024-02-09T02:56:04+00:00",
            action_confirmed=True,
            sent_by="user",
            message_type="interactive",
            message_body=None,
            command="send_callback",
            response_to=tg_message.message_id,
            tg_user_id="mike_mockowitz",
            tg_chat_id=1234,
            tg_message_id="1234-6969",
        )
        assert message == expected_message

    @pytest.mark.asyncio
    @patch(
        "grannymail.integrations.messengers.telegram.Telegram._download_media",
        new_callable=AsyncMock,
    )
    @patch("uuid.uuid4", new_callable=Mock)
    async def test_process_message_media(
        self, mock_uuid4, mock_download_media, fake_uow
    ):
        # setup
        with open("tests/test_data/example_voice_memo.ogg", "rb") as f:
            mock_download_media.return_value = f.read()
        mock_uuid4.return_value = "00000000-0000-0000-0000-000000000000"

        update, context = utils._create_tg_voice_memo_msg()

        # call
        message = await Telegram().process_message(update, context, fake_uow)

        # tests
        expected_message = m.TelegramMessage(
            message_id="00000000-0000-0000-0000-000000000000",
            user_id="00000000-0000-0000-0000-000000000000",
            messaging_platform="Telegram",
            command="voice",
            attachment_mime_type="audio/ogg",
            timestamp="2024-01-26T23:42:09+00:00",
            sent_by="user",
            message_type="audio",
            message_body=None,
            memo_duration=14.1,  # difference
            tg_user_id="mike_mockowitz",
            tg_chat_id=1234,
            tg_message_id="1234-6969",
        )
        # check for media in fake_uow
        assert message == expected_message

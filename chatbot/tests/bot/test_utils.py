import pytest
import grannymail.bot.utils as utils
import grannymail.core.models as dbc
import tests.utils as test_utils
from unittest.mock import AsyncMock
from unittest import mock


# Send a text message to a user on WhatsApp
@pytest.mark.asyncio
@pytest.mark.parametrize("messaging_platform", ["WhatsApp", "Telegram"])
@pytest.mark.usefixtures("mock_send_message_tg")
@mock.patch(
    "grannymail.bot.whatsapp.WhatsappHandler._post_httpx_request",
    new_callable=AsyncMock,
    side_effect=test_utils.generate_whatsapp_httpx_response(start_id=12345),
)
@mock.patch(
    "grannymail.db.supaclient.SupabaseClient.get_last_user_message",
    return_value=dbc.TelegramMessage(tg_chat_id=12345),
)
async def test_send_text_message_to_whatsapp_user(
    mock_get_last_user_message,
    mock_post_httpx_request,
    mock_send_message_tg,
    messaging_platform,
    user,
):
    # Invoke the function under test
    message_body = "test message"
    await utils.send_message(message_body, user.user_id, messaging_platform)

    # Assert that the necessary methods were called with the correct arguments
    if messaging_platform == "Telegram":
        mock_get_last_user_message.assert_called_once_with(
            user, messaging_platform=messaging_platform
        )
    # check that send_message returned a message
    if messaging_platform == "Telegram":
        mock_send_message_tg.assert_called_once_with(chat_id=12345, text=message_body)
    else:
        mock_post_httpx_request.assert_called_once()

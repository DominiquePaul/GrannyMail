import pytest

from grannymail.entrypoints.api.endpoints.telegram import handle_voice_text_or_callback
from tests import utils
from tests.fake_repositories import FakeUnitOfWork


@pytest.mark.asyncio
async def test_telegram_endpoint_help_message(mocker):
    msnger_mock = mocker.patch(
        "grannymail.integrations.messengers.telegram.Telegram.reply_text",
        new_callable=mocker.AsyncMock,
    )
    mocker.patch(
        "grannymail.services.unit_of_work.SupabaseUnitOfWork",
        new_callable=lambda: FakeUnitOfWork,
    )
    # Create a mock request data object
    update, context = utils._create_telegram_text_message_objects("/help")

    # Invoke the webhook_route function
    await handle_voice_text_or_callback(update, context)

    # Assert the response status code and content
    msnger_mock.assert_called_once()

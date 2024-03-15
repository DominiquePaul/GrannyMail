import pytest
from grannymail.entrypoints.api.endpoints.whatsapp import webhook_route
from .utils import _create_whatsapp_text_message
from .fake_repositories import FakeUnitOfWork


@pytest.mark.asyncio
async def test_whatsapp_endpoint_help_message(mocker):
    msnger_mock = mocker.patch(
        "grannymail.integrations.messengers.whatsapp.Whatsapp.reply_text",
        new_callable=mocker.AsyncMock,
    )
    mocker.patch(
        "grannymail.services.unit_of_work.SupabaseUnitOfWork",
        new_callable=lambda: FakeUnitOfWork,
    )
    # Create a mock request data object
    data = _create_whatsapp_text_message(message_body="/help")

    # Invoke the webhook_route function
    response = await webhook_route(data)

    # Assert the response status code and content
    assert response.status_code == 200
    msnger_mock.assert_called_once()

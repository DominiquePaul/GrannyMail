import pytest
from unittest.mock import AsyncMock
from grannymail.telegrambot import handle_voice


@pytest.fixture
def mock_update(mocker):
    update = mocker.Mock()
    update.message.from_user = {"username": "dominique_paul"}
    update.effective_chat.id = 1234
    update.message.voice.file_id = 'fake_file_id'
    return update


@pytest.fixture
def mock_context(mocker):
    context = mocker.Mock()
    context.bot.send_message = AsyncMock()
    context.bot.getFile = AsyncMock()
    context.bot.getFile.return_value.file_path = "https://fake_url.com"
    return context


@pytest.fixture
def mock_requests_get(mocker):
    return mocker.patch('requests.get', return_value=mocker.Mock(content=b'fake_voice_data'))


@pytest.mark.asyncio
async def test_handle_voice(mock_update, mock_context, mock_requests_get):
    await handle_voice(mock_update, mock_context)

    mock_context.bot.send_message.assert_awaited_once_with(
        chat_id=1234, text="A voice memo 😍")
    mock_context.bot.getFile.assert_awaited_once_with('fake_file_id')
    mock_requests_get.assert_called_once_with("https://fake_url.com")

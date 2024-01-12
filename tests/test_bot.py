import pytest
from unittest.mock import AsyncMock, ANY
from grannymail.telegrambot import handle_voice, handle_edit_prompt
from grannymail.db_client import User
from grannymail.utils import get_message


@pytest.fixture
def mock_update():
    update = AsyncMock()
    update.message.from_user = {"username": "mike_mockowitz"}
    update.effective_chat.id = 1234
    update.message.voice.file_id = 'fake_file_id'
    return update


@pytest.fixture
def mock_context():
    context = AsyncMock()
    context.bot.getFile.return_value.file_path = "https://fake_url.com"
    return context


@pytest.fixture
def mock_requests_get(mocker):
    with open("tests/test_data/example_voice_memo.ogg", "rb") as f:
        voice_bytes = f.read()
    return mocker.patch('requests.get', return_value=mocker.Mock(content=voice_bytes))


@pytest.mark.asyncio
async def test_handle_voice(mock_update, mock_context, mock_requests_get, user):
    await handle_voice(mock_update, mock_context)

    mock_context.bot.send_message.assert_awaited_once_with(
        chat_id=1234, text=ANY)
    mock_context.bot.getFile.assert_awaited_once_with('fake_file_id')
    mock_requests_get.assert_called_once_with("https://fake_url.com")


@pytest.mark.asyncio
async def test_handle_edit_prompt(mock_update, mock_context, dbclient, user):
    # setup mocks
    mock_update.message.text = "/edit_prompt use a funny tone"

    # run function
    await handle_edit_prompt(mock_update, mock_context)

    # check results
    expected_text = get_message(
        'edit_prompt_success').format("use a funny tone")

    mock_context.bot.send_message.assert_awaited_once_with(
        chat_id=1234, text=expected_text)
    full_user = dbclient.get_user(User(telegram_id="mike_mockowitz"))
    assert full_user.prompt == "use a funny tone"

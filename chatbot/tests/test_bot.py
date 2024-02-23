from unittest.mock import ANY, AsyncMock, call

import pytest

import grannymail.main as gm
from grannymail.db.classes import Draft, User
from grannymail.db.supaclient import NoEntryFoundError
from grannymail.utils.message_utils import format_address_simple
from grannymail.utils.utils import get_prompt_from_sheet


@pytest.fixture
def mock_update():
    update = AsyncMock()
    update.message.from_user = {"username": "mike_mockowitz"}
    update.effective_chat.id = 1234
    update.message.voice.file_id = "fake_file_id"
    update.message.voice.duration = 10
    return update


@pytest.fixture
def mock_context():
    context = AsyncMock()
    context.bot.getFile.return_value.file_path = "https://fake_url.com"
    return context


# @pytest.fixture
# def mock_requests_get(mocker):
#     with open("tests/test_data/example_voice_memo.ogg", "rb") as f:
#         voice_bytes = f.read()
#     return mocker.patch("requests.get", return_value=mocker.Mock(content=voice_bytes))
#     mock_requests_get.assert_called_once_with("https://fake_url.com")


# @pytest.mark.asyncio
# async def test_handle_help_fails_no_user(mock_update, mock_context):
#     mock_update.message.text = "/help"
#     await gm.handle_help(mock_update, mock_context)

#     mock_context.bot.send_message.assert_awaited_once_with(
#         chat_id=1234, text=get_prompt_from_sheet("system-error-telegram_user_not_found")
#     )


# @pytest.mark.asyncio
# async def test_handle_report_bug_no_message(mock_update, mock_context, user):
#     mock_update.message.text = "/report_bug"
#     await gm.handle_report_bug(mock_update, mock_context)

#     mock_context.bot.send_message.assert_awaited_once_with(
#         chat_id=1234, text=get_prompt_from_sheet("report_bug-error-msg_empty")
#     )


# @pytest.mark.asyncio
# async def test_handle_report_bug_success(mock_update, mock_context, user):
#     mock_update.message.text = "/report_bug no letter created"
#     await gm.handle_report_bug(mock_update, mock_context)

#     mock_context.bot.send_message.assert_awaited_once_with(
#         chat_id=1234, text=get_prompt_from_sheet("report_bug-success")
#     )


# @pytest.mark.asyncio
# async def test_handle_show_address_book(mock_update, mock_context, user):
#     mock_update.message.text = "/show_address_book"
#     await gm.handle_show_address_book(mock_update, mock_context)

#     mock_context.bot.send_message.assert_awaited_once_with(chat_id=1234, text=ANY)


# @pytest.mark.asyncio
# async def test_handle_add_address(
#     mock_update, mock_context, dbclient, user, address_string_correct
# ):
#     # prepare test
#     mock_update.message.text = "/add_address \n" + address_string_correct

#     # function call
#     await gm.handle_add_address(mock_update, mock_context)

#     # check that the response text is correct
#     # address = parse_new_address(address_string_correct)
#     # address_confirmation_format = format_address_for_confirmation(
#     #     address)
#     # response_msg = get_prompt_from_sheet(
#     #     "add_address-success").format(address_confirmation_format)
#     mock_context.bot.send_message.assert_awaited_once_with(
#         chat_id=1234, text=ANY, reply_markup=ANY
#     )

#     # check whether it worked, i.e. the expected substring is present
#     # in the actual text
#     actual_call = mock_context.bot.send_message.await_args_list[0]
#     actual_text = actual_call.kwargs["text"]
#     assert get_prompt_from_sheet("add_address-success")[:10] in actual_text


# @pytest.mark.asyncio
# async def test_handle_add_address_fails_bc_too_short(
#     mock_update, mock_context, dbclient, user, address_string_too_short
# ):
#     # prepare test
#     mock_update.message.text = "/add_address \n" + address_string_too_short

#     # function call
#     await gm.handle_add_address(mock_update, mock_context)
#     mock_context.bot.send_message.assert_awaited_once_with(
#         chat_id=1234, text=get_prompt_from_sheet("add_address-error-too_short")
#     )


# @pytest.mark.asyncio
# async def test_handle_delete_address(
#     mock_update, mock_context, dbclient, user, address
# ):
#     # prepare call
#     user_addresses = dbclient.get_user_addresses(user)
#     mock_update.message.text = f"/delete_address {len(user_addresses)}"

#     # function call
#     await gm.handle_delete_address(mock_update, mock_context)

#     # test
#     expected = get_prompt_from_sheet("delete_address-success")
#     assert mock_context.bot.send_message.await_args_list[0].kwargs["text"] == expected


# @pytest.mark.asyncio
# async def test_handle_voice(mock_update, mock_context, mock_requests_get, user):
#     await gm.handle_voice(mock_update, mock_context)

#     assert mock_context.bot.send_message.await_count == 2
#     mock_context.bot.getFile.assert_awaited_once_with("fake_file_id")
#     mock_requests_get.assert_called_once_with("https://fake_url.com")


# @pytest.mark.asyncio
# async def test_handle_edit_prompt(mock_update, mock_context, dbclient, user):
#     # setup mocks
#     mock_update.message.text = "/edit_prompt use a funny tone"

#     # run function
#     await gm.handle_edit_prompt(mock_update, mock_context)

#     # check results
#     expected_text = dbclient.get_system_message("edit_prompt-success").format(
#         "use a funny tone"
#     )

#     mock_context.bot.send_message.assert_awaited_once_with(
#         chat_id=1234, text=expected_text
#     )
#     full_user = dbclient.get_user(User(telegram_id="mike_mockowitz"))
#     assert full_user.prompt == "use a funny tone"


# @pytest.mark.asyncio
# async def test_handle_edit_draft(mock_update, mock_context, dbclient, user):
#     # prepare mock objects
#     mock_update.message.text = "/edit 'Doris' -> 'Anna'"

#     # Run the function but it should fail because the user does not have any draft saved
#     with pytest.raises(NoEntryFoundError):
#         await gm.handle_edit_draft(mock_update, mock_context)

#     # add a draft
#     draft = Draft(user_id=user.user_id, text="Hallo Doris, mir geht es gut?")
#     dbclient.add_draft(draft)

#     # run function
#     await gm.handle_edit_draft(mock_update, mock_context)

#     # evaluate first response
#     expected1 = get_prompt_from_sheet("edit-confirm")
#     assert mock_context.bot.send_message.await_args_list[0].kwargs["text"] == expected1
#     # evaluate second response
#     second_call_args = mock_context.bot.send_message.call_args_list[1]
#     expected2 = get_prompt_from_sheet("edit-success")
#     assert second_call_args == call(chat_id=1234, text=expected2)

#     mock_context.bot.send_document.assert_awaited_once_with(
#         chat_id=mock_update.effective_chat.id,
#         document=ANY,
#         filename="draft_updated.pdf",
#     )


# @pytest.mark.asyncio
# async def test_handle_send_fails_no_addressee_referenced(
#     mock_update, mock_context, user
# ):
#     # prepare mock objects
#     mock_update.message.text = "/send "

#     # call function
#     await gm.handle_send(mock_update, mock_context)

#     mock_context.bot.send_message.assert_awaited_once_with(
#         chat_id=1234, text=get_prompt_from_sheet("send-error-msg_empty")
#     )


# @pytest.mark.asyncio
# async def test_handle_send_fails_no_previous_draft(
#     mock_update, mock_context, user, address
# ):
#     # prepare mock objects
#     mock_update.message.text = "/send mama"

#     # call function
#     await gm.handle_send(mock_update, mock_context)

#     mock_context.bot.send_message.assert_awaited_once_with(
#         chat_id=1234, text=get_prompt_from_sheet("send-error-no_previous_draft")
#     )


# @pytest.mark.asyncio
# async def test_handle_send_success(
#     mock_update, mock_context, dbclient, user, address, draft
# ):
#     # prepare mock objects
#     mock_update.message.text = "/send mama mockowitz"

#     # call function
#     await gm.handle_send(mock_update, mock_context)

#     # test that the response contains a markup keyboard
#     address_formatted = format_address_simple(address)
#     expected = get_prompt_from_sheet("send-success").format(
#         user.first_name, address_formatted
#     )
#     mock_context.bot.send_message.assert_awaited_once_with(
#         chat_id=1234, reply_markup=ANY, text=expected
#     )
#     # assert mock_context.bot.send_message.await_args_list[0].kwargs["text"] == expected
#     mock_context.bot.send_document.assert_awaited_once_with(
#         chat_id=1234, document=ANY, filename="final_letter.pdf"
#     )

#     # make sure that the message is updated and contains a draft referenced
#     msg = dbclient.get_last_user_message(user)
#     last_draft = dbclient.get_last_draft(user)
#     assert isinstance(msg.draft_referenced, str)
#     assert msg.draft_referenced == last_draft.draft_id

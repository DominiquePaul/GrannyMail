# import typing as t
# import unittest.mock
# from unittest.mock import AsyncMock, MagicMock, patch, ANY, call
# import pytest

# import grannymail.entrypoints.api.endpoints.telegram as gm
# from grannymail.utils.utils import get_prompt_from_sheet
# import tests.utils as test_utils
# import grannymail.utils.message_utils as msg_utils


# def generate_message_response(start_id=1000):
#     while True:
#         yield MagicMock(chat_id=1234, message_id=start_id)
#         start_id += 1


# class TestBase:
#     async def send_and_assert(
#         self,
#         async_client,
#         message_body,
#         patch_target: str,
#         expected_sheet_response: t.Union[str, list[str], None] = None,
#         expected_response_str: t.Union[str, list[str], unittest.mock._ANY, None] = None,
#     ):
#         # Initialize expected_response at the beginning
#         expected_response: list[str] | unittest.mock._ANY = []
#         if expected_sheet_response and expected_response_str:
#             raise ValueError(
#                 "Only one of expected_sheet_response or expected_response_str should be provided"
#             )
#         if not expected_sheet_response and not expected_response_str:
#             raise ValueError(
#                 "One of expected_sheet_response or expected_response_str must be provided"
#             )

#         if expected_sheet_response:
#             expected_response = [
#                 get_prompt_from_sheet(resp)
#                 for resp in (
#                     [expected_sheet_response]
#                     if isinstance(expected_sheet_response, str)
#                     else expected_sheet_response
#                 )
#             ]
#         elif isinstance(expected_response_str, unittest.mock._ANY):
#             expected_response = expected_response_str
#         elif expected_response_str:
#             expected_response = (
#                 expected_response_str
#                 if isinstance(expected_response_str, list)
#                 else [expected_response_str]
#             )

#         message = test_utils.create_whatsapp_text_message(message_body=message_body)
#         with patch(patch_target, new_callable=AsyncMock) as mocked_function:
#             await gm.webhook_route(message)
#             if not isinstance(expected_response, list):
#                 mocked_function.assert_awaited_with(expected_response)
#             elif len(expected_response) == 1:
#                 mocked_function.assert_awaited_with(expected_response[0])
#             else:
#                 calls = [call(resp) for resp in expected_response]
#                 mocked_function.assert_has_awaits(calls)


# class TestTelegram:
#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     async def test_handle_no_command(self, mock_send_message_tg):
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "hey, what is this app about?"
#         )
#         await gm.handle_no_command(mock_update, mock_context)

#         mock_send_message_tg.assert_awaited_once_with(
#             chat_id=1234, text=get_prompt_from_sheet("no_command-success")
#         )

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     async def test_help(self, mock_send_message_tg, user):
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/help"
#         )
#         await gm.handle_help(mock_update, mock_context)
#         mock_send_message_tg.assert_called_once_with(
#             chat_id=1234, text=get_prompt_from_sheet("help-success")
#         )

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     async def test_report_bug(self, mock_send_message_tg, user):
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/report_bug not getting a response after using /send"
#         )
#         await gm.handle_report_bug(mock_update, mock_context)
#         mock_send_message_tg.assert_called_once_with(
#             chat_id=1234, text=get_prompt_from_sheet("report_bug-success")
#         )

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     async def test_report_bug_fails_no_text(self, mock_send_message_tg, user):
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/report_bug"
#         )
#         await gm.handle_report_bug(mock_update, mock_context)
#         mock_send_message_tg.assert_called_once_with(
#             chat_id=1234, text=get_prompt_from_sheet("report_bug-error-msg_empty")
#         )

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     async def test_edit_prompt_fails_no_text(self, mock_send_message_tg, user):
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/edit_prompt  "
#         )
#         await gm.handle_edit_prompt(mock_update, mock_context)
#         mock_send_message_tg.assert_called_once_with(
#             chat_id=1234, text=get_prompt_from_sheet("edit_prompt-error-msg_empty")
#         )

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     async def test_edit_prompt(self, mock_send_message_tg, user, dbclient):
#         new_prompt = "use a soft langauge"
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/edit_prompt " + new_prompt
#         )
#         await gm.handle_edit_prompt(mock_update, mock_context)
#         mock_send_message_tg.assert_called_once_with(
#             chat_id=1234,
#             text=get_prompt_from_sheet("edit_prompt-success").format(new_prompt),
#         )
#         assert dbclient.get_user(user).prompt == new_prompt

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_document_tg")
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     async def test_handle_voice(
#         self, mock_send_message_tg, mock_send_document_tg, user, dbclient, tg_voice_memo
#     ):
#         # Create a mock for the _download_file method
#         # This mock will replace the actual _download_file method in your TelegramHandler class
#         async def mock_download_file(*args, **kwargs):
#             with open("tests/test_data/example_voice_memo.ogg", "rb") as f:
#                 local_voice_bytes = f.read()
#             return local_voice_bytes

#         mock_update = test_utils.create_mock_update(tg_voice_memo)
#         mock_context = AsyncMock()  # Mock the context
#         mock_context.bot.getFile.return_value.file_path = "https://fake_url.com"

#         # Use patch to replace the _download_file method with your mock
#         with patch(
#             "grannymail.bot.telegram.TelegramHandler._download_file",
#             new=mock_download_file,
#         ):
#             # Run command
#             await gm.handle_voice(mock_update, mock_context)

#         # Assertions
#         mock_send_message_tg.assert_any_call(
#             chat_id=1234, text=get_prompt_from_sheet("voice-confirm")
#         )
#         mock_send_message_tg.assert_any_call(
#             chat_id=1234, text=get_prompt_from_sheet("voice-success")
#         )

#         r = (
#             dbclient.client.table("messages")
#             .select("*")
#             .eq("user_id", user.user_id)
#             .neq("transcript", None)
#             .execute()
#         )
#         assert len(r.data) == 1

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     async def test_show_address_book_fail_no_addresses(
#         self, mock_send_message_tg, user
#     ):
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/show_address_book "
#         )
#         await gm.handle_show_address_book(mock_update, mock_context)
#         mock_send_message_tg.assert_awaited_once_with(
#             chat_id=1234,
#             text=get_prompt_from_sheet("show_address_book-error-user_has_no_addresses"),
#         )

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     async def test_show_address_book_success(self, mock_send_message_tg, user, address):
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/show_address_book "
#         )
#         await gm.handle_show_address_book(mock_update, mock_context)
#         mock_send_message_tg.assert_awaited_once_with(chat_id=1234, text=ANY)

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     async def test_add_address(
#         self, mock_send_message_tg, user, address_string_correct
#     ):
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/add_address \n" + address_string_correct
#         )
#         await gm.handle_add_address(mock_update, mock_context)

#         mock_send_message_tg.assert_awaited_once_with(
#             chat_id=1234, text=ANY, reply_markup=ANY
#         )

#         # check whether it worked, i.e. the expected substring is present
#         # in the actual text
#         actual_call = mock_send_message_tg.await_args_list[0]
#         actual_text = actual_call.kwargs["text"]
#         assert get_prompt_from_sheet("add_address-success")[:10] in actual_text

#     #  fixture 'callbackquery_mock_answer' not found

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     @pytest.mark.usefixtures("mock_edit_message_text_tg")
#     @patch("telegram._callbackquery.CallbackQuery.answer", new_callable=AsyncMock)
#     async def test_add_adddress_callback_cancel(
#         self,
#         callbackquery_mock_answer,
#         mock_edit_message_text_tg,
#         mock_send_message_tg,
#         user,
#         address_string_correct,
#     ):
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/add_address \n" + address_string_correct
#         )

#         system_message = await gm.handle_add_address(mock_update, mock_context)
#         assert system_message is not None
#         mock_send_message_tg.assert_awaited_once_with(
#             chat_id=1234, text=ANY, reply_markup=ANY
#         )

#         mock_update, mock_context = test_utils.create_telegram_callback(
#             system_message.message_id, False
#         )
#         await gm.callback_handler(mock_update, mock_context)

#         callbackquery_mock_answer.assert_awaited_once()
#         mock_edit_message_text_tg.assert_awaited_once_with(
#             text=get_prompt_from_sheet("add_address_callback-cancel")
#         )

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     @pytest.mark.usefixtures("mock_edit_message_text_tg")
#     @patch("telegram._callbackquery.CallbackQuery.answer", new_callable=AsyncMock)
#     async def test_add_adddress_callback_confirm(
#         self,
#         callbackquery_mock_answer,
#         mock_edit_message_text_tg,
#         mock_send_message_tg,
#         user,
#         address_string_correct,
#     ):
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/add_address \n" + address_string_correct
#         )

#         system_message = await gm.handle_add_address(mofck_update, mock_context)
#         assert system_message is not None
#         mock_send_message_tg.assert_awaited_once_with(
#             chat_id=1234, text=ANY, reply_markup=ANY
#         )

#         mock_update, mock_context = test_utils.create_telegram_callback(
#             system_message.message_id, True
#         )
#         await gm.callback_handler(mock_update, mock_context)

#         callbackquery_mock_answer.assert_awaited_once()
#         mock_edit_message_text_tg.assert_awaited_once_with(
#             text=get_prompt_from_sheet("add_address_callback-confirm")
#         )

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     async def test_handle_edit_draft_fails_no_previous_draft(
#         self, mock_send_message_tg, user
#     ):
#         # prepare mock objects
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/edit 'Doris' -> 'Anna'"
#         )

#         # Run the function but it should fail because the user does not have any draft saved
#         await gm.handle_edit(mock_update, mock_context)
#         mock_send_message_tg.assert_awaited_once_with(
#             chat_id=1234, text=get_prompt_from_sheet("edit-error-no_draft_found")
#         )

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_document_tg")
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     async def test_handle_edit_draft_success(
#         self, mock_send_message_tg, mock_send_document_tg, user, draft
#     ):
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/edit 'Doris' -> 'Anna'"
#         )

#         await gm.handle_edit(mock_update, mock_context)

#         # evaluate first response
#         assert mock_send_message_tg.await_args_list[0].kwargs[
#             "text"
#         ] == get_prompt_from_sheet("edit-confirm")
#         # evaluate second response
#         second_call_args = mock_send_message_tg.call_args_list[1]
#         assert second_call_args == call(
#             chat_id=1234, text=get_prompt_from_sheet("edit-success")
#         )
#         assert mock_update.effective_chat is not None
#         mock_send_document_tg.assert_awaited_once_with(
#             chat_id=mock_update.effective_chat.id,
#             document=ANY,
#             filename="draft_updated.pdf",
#         )

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     async def test_send_failure_no_message(self, mock_send_message_tg, user):
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/send  "
#         )
#         await gm.handle_send(mock_update, mock_context)
#         mock_send_message_tg.assert_awaited_once_with(
#             chat_id=1234, text=get_prompt_from_sheet("send-error-msg_empty")
#         )

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     async def test_send_failure_no_draft(self, mock_send_message_tg, user):
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/send Justine"
#         )
#         await gm.handle_send(mock_update, mock_context)
#         mock_send_message_tg.assert_awaited_once_with(
#             chat_id=1234, text=get_prompt_from_sheet("send-error-no_draft")
#         )

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     async def test_send_failure_no_addresses(self, mock_send_message_tg, user, draft):
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/send Justine"
#         )
#         await gm.handle_send(mock_update, mock_context)
#         mock_send_message_tg.assert_awaited_once_with(
#             chat_id=1234, text=get_prompt_from_sheet("send-error-user_has_no_addresses")
#         )

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     async def test_send_failure_no_good_address_match(
#         self, mock_send_message_tg, dbclient, user, draft, address
#     ):
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/send Justine"
#         )
#         await gm.handle_send(mock_update, mock_context)

#         # test for correct response
#         address_book = dbclient.get_user_addresses(user)
#         formatted_address_book = msg_utils.format_address_book(address_book)
#         mock_send_message_tg.assert_awaited_once_with(
#             chat_id=1234,
#             text=get_prompt_from_sheet("send-error-no_good_address_match").format(
#                 formatted_address_book
#             ),
#         )

#     @pytest.mark.asyncio
#     @pytest.mark.usefixtures("mock_send_document_tg")
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     async def test_send_success(
#         self, mock_send_message_tg, mock_send_document_tg, user, draft, address
#     ):
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/send Mama Mocko"
#         )
#         await gm.handle_send(mock_update, mock_context)
#         # Check that a document was sent:
#         mock_send_document_tg.assert_awaited_once()
#         # check that a message was sent with a stripe link
#         mock_send_message_tg.assert_awaited_once_with(chat_id=1234, text=ANY)

#     # missing: a test that tests for the case where user has credits

#     @pytest.mark.asyncio
#     @pytest.mark.parametrize("action_confirmed", [True, False])
#     @pytest.mark.usefixtures("mock_edit_message_text_tg")
#     @pytest.mark.usefixtures("mock_send_document_tg")
#     @pytest.mark.usefixtures("mock_send_message_tg")
#     @patch("telegram._callbackquery.CallbackQuery.answer", new_callable=AsyncMock)
#     async def test_send_callback(
#         self,
#         callbackquery_mock_answer,
#         mock_send_message_tg,
#         mock_send_document_tg,
#         mock_edit_message_text_tg,
#         user,
#         draft,
#         address,
#         action_confirmed,
#     ):
#         # 1. Part: Send send request
#         mock_update, mock_context = test_utils.create_telegram_text_message_objects(
#             "/send Mama Mocko"
#         )
#         system_message = await gm.handle_send(mock_update, mock_context)
#         mock_send_message_tg.assert_awaited_once_with(chat_id=1234, text=ANY)

#         # 2. Respond to message
#         assert system_message is not None
#         mock_update, mock_context = test_utils.create_telegram_callback(
#             system_message.message_id, action_confirmed=action_confirmed
#         )

#         await gm.callback_handler(mock_update, mock_context)
#         # checks that the callback was responded to
#         callbackquery_mock_answer.assert_awaited_once()
#         if action_confirmed:
#             expected_text = get_prompt_from_sheet("send_callback-confirm")
#         else:
#             expected_text = get_prompt_from_sheet("send_callback-cancel")
#         mock_edit_message_text_tg.assert_awaited_once_with(text=expected_text)


# class TestWhatsapp(TestBase):
#     @pytest.mark.asyncio
#     async def test_help(self, async_client):
#         await self.send_and_assert(
#             async_client,
#             "/help",
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message",
#             "help-success",
#         )

#     @pytest.mark.asyncio
#     async def test_report_bug(self, async_client):
#         await self.send_and_assert(
#             async_client,
#             "/report_bug not getting a response after using /send",
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message",
#             "report_bug-success",
#         )

#     @pytest.mark.asyncio
#     async def test_report_bug_fails_no_text(self, async_client):
#         await self.send_and_assert(
#             async_client,
#             "/report_bug",
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message",
#             "report_bug-error-msg_empty",
#         )

#     @pytest.mark.asyncio
#     async def test_report_bug_fails_trailing_spaces(self, async_client):
#         await self.send_and_assert(
#             async_client,
#             "/report_bug   ",
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message",
#             "report_bug-error-msg_empty",
#         )

#     @pytest.mark.asyncio
#     async def test_edit_prompt_fails_no_text(self, async_client, user):
#         await self.send_and_assert(
#             async_client,
#             "/edit_prompt   ",
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message",
#             "edit_prompt-error-msg_empty",
#         )

#     @pytest.mark.asyncio
#     async def test_edit_prompt(self, async_client, dbclient, user):
#         new_prompt = "use a simple language"
#         expected_response = get_prompt_from_sheet("edit_prompt-success").format(
#             new_prompt
#         )
#         await self.send_and_assert(
#             async_client,
#             "/edit_prompt use a simple language",
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message",
#             expected_response_str=expected_response,
#         )
#         assert dbclient.get_user(user).prompt == new_prompt

#     @pytest.mark.asyncio
#     @patch(
#         "grannymail.bot.whatsapp.WhatsappHandler.send_document", new_callable=AsyncMock
#     )
#     @patch(
#         "grannymail.bot.whatsapp.WhatsappHandler.send_message", new_callable=AsyncMock
#     )
#     @patch("grannymail.bot.whatsapp.WhatsappHandler._download_media")
#     async def test_handle_voice(
#         self,
#         mock_download_media,
#         mock_send_message,
#         mock_send_document,
#         user,
#         dbclient,
#         wa_voice_memo,
#     ):
#         async def _download_media(*args, **kwargs):
#             with open("tests/test_data/example_voice_memo.ogg", "rb") as f:
#                 return f.read()

#         mock_download_media.side_effect = _download_media
#         await gm.webhook_route(wa_voice_memo)
#         mock_send_message.assert_any_call(get_prompt_from_sheet("voice-confirm"))
#         mock_send_message.assert_any_call(get_prompt_from_sheet("voice-success"))
#         mock_send_document.assert_awaited_once()

#         r = (
#             dbclient.client.table("messages")
#             .select("*")
#             .eq("user_id", user.user_id)
#             .neq("transcript", None)
#             .execute()
#         )
#         assert len(r.data) == 1

#     @pytest.mark.asyncio
#     async def test_show_address_book_fail_no_addresses(self, async_client, user):
#         await self.send_and_assert(
#             async_client,
#             "/show_address_book",
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message",
#             expected_response_str=get_prompt_from_sheet(
#                 "show_address_book-error-user_has_no_addresses"
#             ),
#         )

#     @pytest.mark.asyncio
#     async def test_show_address_book_success(self, async_client, user, address):
#         await self.send_and_assert(
#             async_client,
#             "/show_address_book",
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message",
#             expected_response_str=ANY,
#         )

#     @pytest.mark.asyncio
#     async def test_add_address(self, user, address_string_correct):
#         message = test_utils.create_whatsapp_text_message(
#             message_body="/add_address \n" + address_string_correct
#         )

#         with patch(
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message_confirmation_request",
#             new_callable=AsyncMock,
#         ) as mock_send_message:
#             await gm.webhook_route(message)
#             actual_call = mock_send_message.await_args_list[0]
#             actual_text = actual_call.kwargs["main_msg"]
#             assert get_prompt_from_sheet("add_address-success")[:10] in actual_text

#     @pytest.mark.asyncio
#     @patch(
#         "grannymail.bot.whatsapp.WhatsappHandler._post_httpx_request",
#         new_callable=AsyncMock,
#     )
#     @patch(
#         "grannymail.bot.whatsapp.WhatsappHandler.send_message", new_callable=AsyncMock
#     )
#     async def test_add_adddress_callback_cancel(
#         self, mock_send_message, mock_post_httpx_request, user, address_string_correct
#     ):
#         mock_post_httpx_request.side_effect = (
#             test_utils.generate_whatsapp_httpx_response(start_id=12345)
#         )
#         message1 = test_utils.create_whatsapp_text_message(
#             message_body="/add_address \n" + address_string_correct
#         )
#         await gm.webhook_route(message1)

#         message1_id = "wamid_12345"
#         message2 = test_utils.create_whatsapp_callback_message(message1_id, "false")
#         await gm.webhook_route(message2)
#         mock_send_message.assert_awaited_with(
#             get_prompt_from_sheet("add_address_callback-cancel")
#         )

#     @pytest.mark.asyncio
#     @patch(
#         "grannymail.bot.whatsapp.WhatsappHandler._post_httpx_request",
#         new_callable=AsyncMock,
#     )
#     @patch(
#         "grannymail.bot.whatsapp.WhatsappHandler.send_message", new_callable=AsyncMock
#     )
#     async def test_add_adddress_callback_confirm(
#         self, mock_send_message, mock_post_httpx_request, user, address_string_correct
#     ):
#         message1_id = "wamid_12345"
#         mock_post_httpx_request.side_effect = (
#             test_utils.generate_whatsapp_httpx_response(start_id=12345)
#         )
#         message1 = test_utils.create_whatsapp_text_message(
#             message_body="/add_address \n" + address_string_correct
#         )
#         await gm.webhook_route(message1)

#         message2 = test_utils.create_whatsapp_callback_message(message1_id, "true")
#         await gm.webhook_route(message2)

#         first_call = mock_send_message.await_args_list[0]
#         second_call = mock_send_message.await_args_list[1]

#         assert first_call == call(get_prompt_from_sheet("add_address_callback-confirm"))
#         assert (
#             get_prompt_from_sheet("add_address_callback-success-follow_up").replace(
#                 "{}", ""
#             )
#             in second_call.args[0]
#         )

#     @pytest.mark.asyncio
#     async def test_handle_delete_address_numeric_idx(
#         self, async_client, dbclient, user, address, address2
#     ):
#         response1 = get_prompt_from_sheet("delete_address-success")
#         address_book = dbclient.get_user_addresses(user)
#         formatted_address_book = msg_utils.format_address_book([address_book[1]])
#         response2 = get_prompt_from_sheet("delete_address-success-follow_up").format(
#             formatted_address_book
#         )
#         await self.send_and_assert(
#             async_client,
#             "/delete_address 1",
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message",
#             expected_response_str=[response1, response2],
#         )
#         assert len(dbclient.get_user_addresses(user)) == 1
#         assert dbclient.get_user_addresses(user)[0] == address2

#     @pytest.mark.asyncio
#     async def test_handle_edit_draft_fails_no_previous_draft(self, user, async_client):
#         await self.send_and_assert(
#             async_client,
#             "/edit 'Doris' -> 'Anna'",
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message",
#             "edit-error-no_draft_found",
#         )

#     @pytest.mark.asyncio
#     async def test_handle_edit_draft_success(self, user, draft, dbclient):
#         message = test_utils.create_whatsapp_text_message(
#             message_body="/edit 'Doris' -> 'Anna'"
#         )

#         with patch(
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message",
#             new_callable=AsyncMock,
#         ) as mock_send_message:
#             with patch(
#                 "grannymail.bot.whatsapp.WhatsappHandler.send_document",
#                 new_callable=AsyncMock,
#             ) as mock_send_document:
#                 await gm.webhook_route(message)
#                 second_call_args = mock_send_message.call_args_list[1]
#                 assert second_call_args == call(
#                     message_body=get_prompt_from_sheet("edit-success")
#                 )
#                 mock_send_document.assert_awaited_once()

#         # check that a new document was added to the DB
#         r = (
#             dbclient.client.table("drafts")
#             .select("*")
#             .eq("user_id", user.user_id)
#             .execute()
#         )
#         assert len(r.data) == 2

#     @pytest.mark.asyncio
#     async def test_send_failure_no_message(self, async_client, user):
#         await self.send_and_assert(
#             async_client,
#             "/send\n",
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message",
#             "send-error-msg_empty",
#         )

#     @pytest.mark.asyncio
#     async def test_send_failure_no_draft(self, async_client, user):
#         await self.send_and_assert(
#             async_client,
#             "/send\nJustine",
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message",
#             "send-error-no_draft",
#         )

#     @pytest.mark.asyncio
#     async def test_send_failure_no_addresses(self, async_client, user, draft):
#         await self.send_and_assert(
#             async_client,
#             "/send\nJustine",
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message",
#             "send-error-user_has_no_addresses",
#         )

#     @pytest.mark.asyncio
#     async def test_send_failure_no_good_address_match(
#         self, async_client, dbclient, user, draft, address
#     ):
#         address_book = dbclient.get_user_addresses(user)
#         formatted_address_book = msg_utils.format_address_book(address_book)
#         expected_response = get_prompt_from_sheet(
#             "send-error-no_good_address_match"
#         ).format(formatted_address_book)
#         await self.send_and_assert(
#             async_client,
#             "/send\nJustine",
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message",
#             expected_response_str=expected_response,
#         )

#     @pytest.mark.asyncio
#     @patch(
#         "grannymail.bot.whatsapp.WhatsappHandler.send_document", new_callable=AsyncMock
#     )
#     @patch(
#         "grannymail.bot.whatsapp.WhatsappHandler.send_message", new_callable=AsyncMock
#     )
#     async def test_send_success(
#         self, mock_send_message, mock_send_document, async_client, user, draft, address
#     ):
#         message = test_utils.create_whatsapp_text_message(
#             message_body="/send Mama Mocko"
#         )
#         # execute command
#         await gm.webhook_route(message)
#         # Check that a document was sent:
#         mock_send_document.assert_awaited_once()
#         # check that the send success message was sent
#         mock_send_message.assert_awaited_once()
#         actual_text = mock_send_message.await_args_list[0].args[0]
#         assert get_prompt_from_sheet("send-success-one_off")[:50] in actual_text

#     @pytest.mark.asyncio
#     @pytest.mark.parametrize("action_confirmed", [True, False])
#     @patch(
#         "grannymail.bot.whatsapp.WhatsappHandler._post_httpx_request",
#         new_callable=AsyncMock,
#     )
#     @patch(
#         "grannymail.bot.whatsapp.WhatsappHandler._upload_media",
#         return_value={"id": "random_media_id_1234"},
#     )
#     async def test_send_callback(
#         self,
#         mock_upload_media,
#         mock_post_httpx_request,
#         user,
#         draft,
#         address,
#         action_confirmed,
#     ):
#         mock_post_httpx_request.side_effect = (
#             test_utils.generate_whatsapp_httpx_response(start_id=12345)
#         )
#         message1_id = "wamid_12345"
#         message = test_utils.create_whatsapp_text_message(
#             message_body="/send Mama Mocko"
#         )
#         await gm.webhook_route(message)

#         # 2. Respond to message
#         action_confirmed_str = "true" if action_confirmed else "false"
#         message2 = test_utils.create_whatsapp_callback_message(
#             message1_id, action_confirmed_str
#         )
#         with patch(
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message",
#             new_callable=AsyncMock,
#         ) as mock_send_message:
#             await gm.webhook_route(message2)
#             if action_confirmed:
#                 expected_text = get_prompt_from_sheet("send_callback-confirm")
#             else:
#                 expected_text = get_prompt_from_sheet("send_callback-cancel")
#             mock_send_message.assert_awaited_once_with(expected_text)

#     @pytest.mark.asyncio
#     @patch(
#         "grannymail.bot.whatsapp.WhatsappHandler.send_message", new_callable=AsyncMock
#     )
#     @patch(
#         "grannymail.bot.whatsapp.WhatsappHandler.send_document", new_callable=AsyncMock
#     )
#     @patch(
#         "grannymail.utils.message_utils.transcribe_voice_memo", new_callable=AsyncMock
#     )
#     @patch("grannymail.bot.whatsapp.WhatsappHandler._download_media")
#     async def test_voice_memo_non_latin_alphabet(
#         self,
#         mock_download_media,
#         transcribe_voice_memo,
#         mock_send_document,
#         mock_send_message,
#         user,
#         dbclient,
#         wa_voice_memo,
#     ):
#         async def _download_media(*args, **kwargs):
#             with open("tests/test_data/example_voice_memo.ogg", "rb") as f:
#                 return f.read()

#         mock_download_media.side_effect = _download_media

#         transcribe_voice_memo.return_value = "チャンネル登録をお願いいたします"

#         await gm.webhook_route(wa_voice_memo)
#         assert mock_send_message.call_args_list[1] == call(
#             get_prompt_from_sheet("voice-error-characters_not_supported")
#         )

#     @pytest.mark.asyncio
#     async def test_handle_command_not_found(self, async_client):
#         await self.send_and_assert(
#             async_client,
#             "/sned",
#             "grannymail.bot.whatsapp.WhatsappHandler.send_message",
#             expected_sheet_response="commmand_not_recognised-success",
#         )

import typing as t
from datetime import timedelta
import asyncio
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, call, patch

import pytest

import tests.utils as utils
from grannymail.integrations.messengers import telegram, whatsapp
from grannymail.services.message_processing_service import MessageProcessingService
from grannymail.utils import message_utils
from grannymail.utils.utils import get_utc_timestamp
import grannymail.config as cfg

# test most functions -> ideally use codiume


async def assert_message_received_correct_responses(
    platform: str,
    fake_uow,
    messages: dict[t.Literal["message", "callback", "voice"], dict],
    msg_responses: dict[str, list[str]] = {},
    button_responses: dict[str, list[str]] = {},
    edit_text_responses: dict[str, list] = {},
    sent_document=False,
):
    messenger = whatsapp.Whatsapp() if platform == "WhatsApp" else telegram.Telegram()

    voice_memo_bytes = open("tests/test_data/example_voice_memo.ogg", "rb").read()

    if platform == "WhatsApp":
        patch_target = (
            "grannymail.integrations.messengers.whatsapp.Whatsapp._post_httpx_request"
        )
        patch_return_value = {"messages": [{"id": "some_message_id"}]}
    else:  # Telegram
        patch_target = "telegram.ext._extbot.ExtBot.sendMessage"
        patch_return_value = MagicMock(chat_id="12345", message_id="67890")

    responses = []

    with patch(
        patch_target, new_callable=AsyncMock, return_value=patch_return_value
    ) as mock_patch, patch(
        "telegram._callbackquery.CallbackQuery.answer", new_callable=AsyncMock
    ) as mock_callback_answer:
        with patch.object(
            messenger, "reply_text", new=AsyncMock()
        ) as mock_reply_text, patch.object(
            messenger, "reply_edit_or_text", new=AsyncMock()
        ) as mock_reply_edit_or_text, patch.object(
            messenger, "_download_media", new=AsyncMock(return_value=voice_memo_bytes)
        ) as mock_download_media, patch.object(
            messenger, "reply_document", new=AsyncMock()
        ) as mock_reply_document:
            # iterate over message calls
            for message_type, kwargs in messages.items():
                if message_type == "message":
                    wa_data, update, context = utils.create_text_message(
                        platform, **kwargs
                    )
                elif message_type == "callback":
                    wa_data, update, context = utils.create_callback_message(
                        platform, **kwargs
                    )
                elif message_type == "voice":
                    wa_data, update, context = utils.create_voice_memo_msg(platform)
                else:
                    raise ValueError("Message type not recognized")

                response = await MessageProcessingService().receive_and_process_message(
                    fake_uow, messenger, update, context, wa_data
                )
                responses.append(response)

    for identifier, insertions in msg_responses.items():
        expected_msg = fake_uow.system_messages.get_msg(identifier).format(*insertions)
        # It's letter time. Pay for the postage via the link below and your letter will be sent 🪄\n\nYou can also buy credits at a discount using the /buy_credits command 💸💳\n\nhttps://buy.stripe.com/test_5kAaIy5FJ9gUes05kl?client_reference_id=221fc420-d112-42b4-b953-3651e1ad95ad
        # It's letter time. Pay for the postage via the link below and your letter will be sent 🪄\n\nYou can also buy credits at a discount using the /buy_credits command 💸💳\n\nhttps://buy.stripe.com/test_5kAaIy5FJ9gUes05kl

        mock_reply_text.assert_any_await(ANY, expected_msg, fake_uow)

    for identifier, insertions in button_responses.items():
        expected_msg = fake_uow.system_messages.get_msg(identifier).format(*insertions)
        # callback case
        if platform == "Telegram":
            mock_patch.assert_any_await(
                chat_id=ANY, reply_markup=ANY, text=expected_msg
            )
        elif platform == "WhatsApp":
            assert (
                mock_patch.call_args.kwargs["data"]["interactive"]["body"]["text"]
                == expected_msg
            )
        else:
            raise ValueError("Platform not recognized")

    for identifier, insertions in edit_text_responses.items():
        expected_msg = fake_uow.system_messages.get_msg(identifier).format(*insertions)
        mock_reply_edit_or_text.assert_any_await(ANY, expected_msg, fake_uow)

    if sent_document:
        mock_reply_document.assert_awaited_once()

    return responses


class TestMessageProcessingService:
    def test_is_message_empty(self, wa_message):
        mps = MessageProcessingService()

        # test1
        wa_message.message_body = None
        assert mps._is_message_empty(wa_message) is True

        # test2
        wa_message.message_body = ""
        assert mps._is_message_empty(wa_message) is True

        # test3
        wa_message.message_body = "     "
        assert mps._is_message_empty(wa_message) is True

        # test4
        wa_message.message_body = " hi   "
        assert mps._is_message_empty(wa_message) is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_process_no_command(self, platform, fake_uow):
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "hey, what's up?"}},
            msg_responses={"no_command-success": []},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_process_unknown_command(self, platform, fake_uow):
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/sned Doris"}},
            msg_responses={"unknown_command-success": ["send"]},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_help(self, platform, fake_uow):
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/help  "}},
            msg_responses={"help-success": []},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_report_bug_no_comment(self, platform, fake_uow):
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/report_bug I'm not getting a draft"}},
            msg_responses={"report_bug-success": []},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_report_bug_with_comment(self, platform, fake_uow):
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/report_bug  "}},
            msg_responses={"report_bug-error-msg_empty": []},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_edit_prompt_happy(self, platform, fake_uow):
        new_prompt = "make my letter rhyme"
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": f"/edit_prompt {new_prompt}"}},
            msg_responses={"edit_prompt-success": [new_prompt]},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_edit_prompt_error_no_text(self, platform, fake_uow):
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/edit_prompt  "}},
            msg_responses={"edit_prompt-error-msg_empty": []},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_voice(self, platform, fake_uow):
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"voice": {}},
            msg_responses={"voice-confirm": [], "voice-success": []},
            sent_document=True,
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_edit_error_no_instructions(self, platform, fake_uow):
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/edit  "}},
            msg_responses={"edit-confirm": [], "edit-error-msg_empty": []},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_edit_error_no_previous_draft(self, platform, fake_uow):
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/edit  doris -> dominique"}},
            msg_responses={"edit-confirm": [], "edit-error-no_draft_found": []},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_edit_happy(self, platform, fake_uow, user, draft):
        fake_uow.users.add(user)
        fake_uow.drafts.add(draft)
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/edit doris -> dominique "}},
            msg_responses={"edit-confirm": [], "edit-success": []},
            sent_document=True,
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_show_address_book_no_addresses(
        self, platform, fake_uow, draft, user
    ):
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/show_address_book  "}},
            msg_responses={"show_address_book-error-user_has_no_addresses": []},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_show_address_book_happy(
        self, platform, fake_uow, user, address
    ):
        fake_uow.users.add(user)
        fake_uow.addresses.add(address)
        add_book = message_utils.format_address_book([address])
        first_name = address.addressee.split(" ")[0]
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/show_address_book  "}},
            msg_responses={"show_address_book-success": [add_book, first_name]},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_add_address(
        self, platform, fake_uow, user, address_string_correct, address
    ):
        fake_uow.users.add(user)
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={
                "message": {"user_msg": "/add_address \n" + address_string_correct}
            },
            button_responses={
                "add_address-success": [address.format_for_confirmation()]
            },
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_add_address_callback(
        self, platform, fake_uow, user, address_string_correct, address
    ):
        fake_uow.users.add(user)
        response = await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={
                "message": {"user_msg": "/add_address \n" + address_string_correct}
            },
            button_responses={
                "add_address-success": [address.format_for_confirmation()]
            },
        )
        reference_message_id = (
            response[0].message_id if platform == "Telegram" else response[0].wa_mid
        )

        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={
                "callback": {
                    "reference_message_id": reference_message_id,
                    "action_confirmed": "true",
                }
            },
            edit_text_responses={"add_address_callback-confirm": []},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_delete_address_no_message(
        self, platform, fake_uow, user, address, address2
    ):
        fake_uow.users.add(user)
        fake_uow.addresses.add(address)
        address2.created_at = get_utc_timestamp(delta=timedelta(days=1))
        fake_uow.addresses.add(address2)
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/delete_address  "}},
            msg_responses={"delete_address-error-msg_empty": []},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_delete_address_invalid_idx(
        self, platform, fake_uow, user, address, address2
    ):
        fake_uow.users.add(user)
        fake_uow.addresses.add(address)
        address2.created_at = get_utc_timestamp(delta=timedelta(days=1))
        fake_uow.addresses.add(address2)
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/delete_address  3"}},
            msg_responses={"delete_address-error-invalid_idx": []},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_delete_address_very_bad_keyword(
        self, platform, fake_uow, user, address, address2
    ):
        fake_uow.users.add(user)
        fake_uow.addresses.add(address)
        address2.created_at = get_utc_timestamp(delta=timedelta(days=1))
        fake_uow.addresses.add(address2)
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/delete_address  dfgsfscdgsdg"}},
            msg_responses={"delete_address-error-invalid_idx": []},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_delete_address_integer(
        self, platform, fake_uow, user, address, address2
    ):
        fake_uow.users.add(user)
        fake_uow.addresses.add(address)
        address2.created_at = get_utc_timestamp(delta=timedelta(days=1))

        fake_uow.addresses.add(address2)
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/delete_address 1"}},
            msg_responses={
                "delete_address-success": [],
                "delete_address-success-follow_up": [
                    message_utils.format_address_book([address2])
                ],
            },
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_delete_address_keyword(
        self, platform, fake_uow, user, address, address2
    ):
        fake_uow.users.add(user)
        fake_uow.addresses.add(address)
        address2.created_at = get_utc_timestamp()
        fake_uow.addresses.add(address2)
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/delete_address Yankee"}},
            msg_responses={
                "delete_address-success": [],
                "delete_address-success-follow_up": [
                    message_utils.format_address_book([address])
                ],
            },
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_send_no_draft(self, platform, fake_uow):
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/send Mama"}},
            msg_responses={"send-error-no_draft": []},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_send_no_addresses(self, platform, fake_uow, user, draft):

        fake_uow.users.add(user)
        fake_uow.drafts.add(draft)
        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/send Mama"}},
            msg_responses={"send-error-user_has_no_addresses": []},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_send_bad_keyword(
        self, platform, fake_uow, user, address, address2, draft
    ):
        fake_uow.users.add(user)
        fake_uow.addresses.add(address)
        address2.created_at = get_utc_timestamp(delta=timedelta(days=1))
        fake_uow.addresses.add(address2)
        fake_uow.drafts.add(draft)
        address_book = message_utils.format_address_book([address, address2])

        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/send Doris"}},
            msg_responses={"send-error-no_good_address_match": [address_book]},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    @patch("uuid.uuid4", new_callable=Mock)
    async def test_handle_send_no_credits(
        self, uuid, platform, fake_uow, user, address, draft
    ):
        uuid.return_value = "221fc420-d112-42b4-b953-3651e1ad95ad"
        fake_uow.users.add(user)
        fake_uow.addresses.add(address)
        fake_uow.drafts.add(draft)

        full_stripe_link1 = (
            cfg.STRIPE_LINK_SINGLE_PAYMENT
            + "?client_reference_id="
            + str("221fc420-d112-42b4-b953-3651e1ad95ad")
        )
        full_stripe_link2 = (
            cfg.STRIPE_LINK_5_CREDITS
            + "?client_reference_id="
            + str("221fc420-d112-42b4-b953-3651e1ad95ad")
        )
        full_stripe_link3 = (
            cfg.STRIPE_LINK_10_CREDITS
            + "?client_reference_id="
            + str("221fc420-d112-42b4-b953-3651e1ad95ad")
        )

        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/send Mama"}},
            msg_responses={
                "send-success-one_off": [
                    full_stripe_link1,
                    full_stripe_link2,
                    full_stripe_link3,
                ]
            },
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_send_purchase_with_credits(
        self, platform, fake_uow, user, address, draft
    ):
        user.num_letter_credits = 2
        fake_uow.users.add(user)
        fake_uow.addresses.add(address)
        fake_uow.drafts.add(draft)

        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/send Mama"}},
            button_responses={
                "send-success-credits": [
                    " " + user.first_name,
                    str(user.num_letter_credits),
                    address.format_address_as_string(),
                ]
            },
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_send_with_credits_callback_confirm(
        self, platform, fake_uow, user, address, draft
    ):
        user.num_letter_credits = 2
        fake_uow.users.add(user)
        fake_uow.addresses.add(address)
        fake_uow.drafts.add(draft)

        responses = await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/send Mama"}},
            button_responses={
                "send-success-credits": [
                    " " + user.first_name,
                    str(user.num_letter_credits),
                    address.format_address_as_string(),
                ]
            },
        )

        reference_message_id = (
            responses[0].message_id if platform == "Telegram" else responses[0].wa_mid
        )

        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={
                "callback": {
                    "reference_message_id": reference_message_id,
                    "action_confirmed": "true",
                }
            },
            edit_text_responses={"send_callback-confirm": []},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
    async def test_handle_send_with_credits_callback_cancel(
        self, platform, fake_uow, user, address, draft
    ):
        user.num_letter_credits = 2
        fake_uow.users.add(user)
        fake_uow.addresses.add(address)
        fake_uow.drafts.add(draft)

        responses = await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={"message": {"user_msg": "/send Mama"}},
            button_responses={
                "send-success-credits": [
                    " " + user.first_name,
                    str(user.num_letter_credits),
                    address.format_address_as_string(),
                ]
            },
        )

        reference_message_id = (
            responses[0].message_id if platform == "Telegram" else responses[0].wa_mid
        )

        await assert_message_received_correct_responses(
            platform,
            fake_uow,
            messages={
                "callback": {
                    "reference_message_id": reference_message_id,
                    "action_confirmed": "false",
                }
            },
            edit_text_responses={"send_callback-cancel": []},
        )


# test with instant payment

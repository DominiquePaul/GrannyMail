from unittest.mock import ANY, patch

import pytest

from grannymail.entrypoints.api.endpoints.payment import process_stripe_event


@pytest.mark.asyncio
@pytest.mark.parametrize("was_dispatched", [True, False])
@pytest.mark.parametrize("platform", ["WhatsApp", "Telegram"])
@patch("grannymail.integrations.stripe_payments.handle_event")
async def test_process_stripe_event(
    mock_handle_event, platform, was_dispatched, fake_uow, wa_message, tg_message
):

    # setup
    ref_message = wa_message if platform == "WhatsApp" else tg_message
    mock_handle_event.return_value = (was_dispatched, ref_message, 10, 12)

    # call
    messenger_module = "whatsapp" if platform == "WhatsApp" else "telegram"
    messenger_class = "Whatsapp" if platform == "WhatsApp" else "Telegram"
    with patch(
        f"grannymail.integrations.messengers.{messenger_module}.{messenger_class}.reply_text"
    ) as mock_messenger:
        await process_stripe_event({}, fake_uow)

    # assertions
    if was_dispatched:
        msg_id = "stripe_webhook-success"
    else:
        msg_id = "stripe_webhook-success-no_dispatch"
    msg = fake_uow.system_messages.get_msg(msg_id).format(10, 12)
    mock_messenger.assert_called_once_with(ANY, msg, fake_uow)

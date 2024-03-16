import pytest
from unittest.mock import patch, AsyncMock

import grannymail.domain.models as m
import grannymail.integrations.stripe_payments as sp


@pytest.mark.parametrize("dispatch_status", [True, False])
def test_handle_event(dispatch_status, fake_uow, user, wa_message, order):
    if dispatch_status:
        order.status = "payment_pending"
    else:
        order.status = "paid"
    with fake_uow:
        fake_uow.users.add(user)
        fake_uow.wa_messages.add(wa_message)
        fake_uow.orders.add(order)

    # Set up the event
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": order.order_id,
                "payment_link": "plink_1Oo9zHLuDIWxSZxaQAbFlPrQ",
            }
        },
    }

    # Invoke the function under test
    with fake_uow, patch(
        "grannymail.integrations.pingen.Pingen.upload_and_send_letter"
    ):
        fake_uow.drafts_blob.download = AsyncMock(return_value=b"blob-blob-blob")
        was_dispatched, ref_message, new_credits, credit_balance = sp.handle_event(
            event, fake_uow
        )

    # test output
    assert was_dispatched == dispatch_status
    assert isinstance(ref_message, m.WhatsappMessage) or isinstance(
        ref_message, m.TelegramMessage
    )
    assert new_credits == 1
    if was_dispatched:
        assert credit_balance == 0
    else:
        assert credit_balance == 1

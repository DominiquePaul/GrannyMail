import uuid
import grannymail.db.classes as dbc
import grannymail.stripe_payments as sp
from unittest.mock import patch


@patch("grannymail.pingen.dispatch_order")
def test_process_order_and_order_found(mock_dispatch_order, dbclient, user, draft):
    # Mock the necessary dependencies
    message = dbclient.add_message(
        dbc.Message(message_body="/send Doris", messaging_platform="WhatsApp")
    )
    order = dbclient.add_order(
        dbc.Order(
            user_id=user.user_id,
            message_id=message.message_id,
            draft_id=draft.draft_id,
            address_id=draft.address_id,
        )
    )
    mock_dispatch_order.return_value = order

    # Set up the event
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": order.order_id,
                "payment_link_id": "plink_1Oo9zHLuDIWxSZxaQAbFlPrQ",
            }
        },
    }

    # Invoke the function under test
    result = sp.handle_event(event)

    # Assert the expected behavior
    assert result == (
        dbclient.get_system_message("send-success-one_off"),
        user.user_id,
        "WhatsApp",
    )

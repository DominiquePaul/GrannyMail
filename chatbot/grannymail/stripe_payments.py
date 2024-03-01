import typing as t
import stripe
from grannymail.db.supaclient import SupabaseClient
from grannymail.logger import logger
import grannymail.db.classes as dbc
import grannymail.config as cfg
import grannymail.pingen as pingen

stripe.api_key = cfg.STRIPE_API_KEY
dbclient = SupabaseClient()


def _add_credits_to_user(user_id: str, num_credits: int) -> None:
    user = dbclient.get_user(dbc.User(user_id=user_id))
    user_copy = user.copy()
    user_copy.num_letter_credits += num_credits
    dbclient.update_user(user, user_copy)


def get_credits_bought(payment_link_id: str) -> int:
    items_bought = stripe.PaymentLink.list_line_items(payment_link_id)["data"]
    total_credits = 0
    for item in items_bought:
        item_dict = t.cast(dict[str, t.Any], item)
        product_id = item_dict["price"]["product"]
        product = stripe.Product.retrieve(product_id)
        letter_credits = product["metadata"]["letter_credits"]
        total_credits += int(letter_credits)
    return total_credits


def get_formated_stripe_link(
    num_credits: int, client_reference_id: str, one_off: bool = False
) -> str:
    if one_off == True and num_credits != 1:
        raise ValueError("One off payment can only be for one credit")
    if one_off:
        body = cfg.STRIPE_LINK_SINGLE_PAYMENT
    else:
        if num_credits == 5:
            body = cfg.STRIPE_LINK_5_CREDITS
        elif num_credits == 10:
            body = cfg.STRIPE_LINK_5_CREDITS
        else:
            raise ValueError(
                "Invalid number of credits. Options are [5,10]. Function was called with '{num_credits}'"
            )
    suffix = f"?client_reference_id={client_reference_id}"
    return body + suffix


def handle_event(event: dict) -> tuple[str, str, str]:
    # Process the event
    if event["type"] == "checkout.session.completed":
        checkout_info = event["data"]["object"]
        client_reference_id = checkout_info.get("client_reference_id")
        order = dbclient.get_order(dbc.Order(order_id=client_reference_id))
        message = dbclient.get_message(dbc.Message(message_id=client_reference_id))
        if order is not None and message is not None:
            raise ValueError(f"Order and User found for same ID: {client_reference_id}")
        elif order is not None:
            # case: one-off payment was made. crid is an order id.
            order = pingen.dispatch_order(order_id=client_reference_id)
            messaging_platform = dbclient.get_message(
                dbc.Message(message_id=order.message_id)
            ).messaging_platform
            message_body = dbclient.get_system_message("send-success-one_off")
            user_id = order.user_id
            item = "One-off payment"
        elif message is not None:
            # This part is not working yet because the /buy_credits command is missing
            payment_link_id = checkout_info["payment_link_id"]
            num_credits = get_credits_bought(payment_link_id)
            assert message.user_id is not None
            _add_credits_to_user(message.user_id, num_credits)
            messaging_platform = message.messaging_platform
            message_body = dbclient.get_system_message("lorem")
            user_id = message.user_id
            item = "{num_credits} Credit(s)"
        else:
            raise ValueError("No order or user found for ID: {client_reference_id}")

        user = dbclient.get_user(dbc.User(user_id=user_id))
        if user.phone_number is not None:
            user_identifier = f"phone number {user.phone_number}"
        elif user.telegram_id is not None:
            user_identifier = f"Telegram ID {user.telegram_id}"
        else:
            user_identifier = "[no user information]"
        logger.info(f"Payment received for {item} by user with {user_identifier}")
        assert user_id is not None
        assert messaging_platform is not None
        return message_body, user_id, messaging_platform
    else:
        raise ValueError(f"Invalid event type: {event['type']}")


if __name__ == "__main__":
    plink = "plink_1Oo9zHLuDIWxSZxaQAbFlPrQ"
    print(get_credits_bought(plink))

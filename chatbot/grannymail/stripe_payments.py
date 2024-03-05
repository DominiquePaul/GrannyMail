import typing as t
import stripe
from grannymail.logger import logger
import grannymail.db.classes as dbc
import grannymail.config as cfg
import grannymail.pingen as pingen
import grannymail.db.repositories as repos

stripe.api_key = cfg.STRIPE_API_KEY
supaclient = repos.create_supabase_client()


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
        user_repo = repos.UserRepository(supaclient)
        order_repo = repos.OrderRepository(supaclient)
        message_repo = repos.MessagesRepository(supaclient)
        system_message_repo = repos.SystemMessageRepository(supaclient)

        checkout_info = event["data"]["object"]
        client_reference_id = checkout_info.get("client_reference_id")
        order = order_repo.maybe_get_one(client_reference_id)
        message = message_repo.maybe_get_one(client_reference_id)
        if order is not None and message is not None:
            raise ValueError(f"Order and User found for same ID: {client_reference_id}")
        elif order is not None:
            # case: one-off payment was made. crid is an order id.
            order = pingen.dispatch_order(order_id=client_reference_id)
            messaging_platform = message_repo.get(order.message_id).messaging_platform
            message_body = system_message_repo.get("send-success-one_off").message_body
            user_id = order.user_id
            item = "One-off payment"
        elif message is not None:
            # This part is not working yet because the /buy_credits command is missing
            payment_link_id = checkout_info["payment_link_id"]
            num_credits = get_credits_bought(payment_link_id)
            assert message.user_id is not None

            # add credits to user's account
            user_id = message.user_id
            user = user_repo.get(message.user_id)
            user.num_letter_credits += num_credits
            user_repo.update(user)

            messaging_platform = message.messaging_platform
            message_body = system_message_repo.get("lorem").message_body
            item = f"{num_credits} Credit(s)"
        else:
            raise ValueError("No order or user found for ID: {client_reference_id}")

        user = user_repo.get(user_id)
        if user.phone_number is not None:
            user_identifier = f"phone number {user.phone_number}"
        elif user.telegram_id is not None:
            user_identifier = f"Telegram ID {user.telegram_id}"
        else:
            user_identifier = "[no user information]"
        logger.info(f"Payment received for {item} by user with {user_identifier}")
        return message_body, user_id, messaging_platform
    else:
        raise ValueError(f"Invalid event type: {event['type']}")


if __name__ == "__main__":
    plink = "plink_1Oo9zHLuDIWxSZxaQAbFlPrQ"
    print(get_credits_bought(plink))

import typing as t

import stripe

import grannymail.config as cfg
import grannymail.domain.models as m
from grannymail.logger import logger
from grannymail.services.unit_of_work import AbstractUnitOfWork

stripe.api_key = cfg.STRIPE_API_KEY


def get_formatted_stripe_link(num_credits: int, client_reference_id: str) -> str:
    """
    Generates a formatted Stripe payment link based on the number of credits and client reference ID.

    Args:
        num_credits (int): The number of credits for which the payment link is generated.
        client_reference_id (str): The client reference ID to be appended to the payment link.

    Returns:
        str: The formatted Stripe payment link.

    Raises:
        ValueError: If the number of credits is not supported.
    """
    credit_link_map = {
        1: cfg.STRIPE_LINK_SINGLE_PAYMENT,
        5: cfg.STRIPE_LINK_5_CREDITS,
        10: cfg.STRIPE_LINK_10_CREDITS,
    }

    body = credit_link_map.get(num_credits)
    if not body:
        raise ValueError(
            f"Invalid number of credits. Options are [1, 5, 10]. Function was called with '{num_credits}'"
        )

    suffix = f"?client_reference_id={client_reference_id}"
    return body + suffix


def handle_event(
    stripe_event: dict, uow: AbstractUnitOfWork
) -> tuple[bool, m.WhatsappMessage | m.TelegramMessage, int, int]:
    """
    Handles a Stripe event, processing payments for orders or credit purchases.

    Args:
        stripe_event (dict): The Stripe event to be processed.
        uow (AbstractUnitOfWork): The unit of work abstraction to manage database transactions.

    Returns:
        tuple[str, m.Message]: A tuple containing the type of payment and the original message related to the payment.

    Raises:
        ValueError: If the event type is not supported or if no order or user is found for the provided ID.
    """
    if stripe_event["type"] != "checkout.session.completed":
        raise ValueError(f"Invalid event type: {stripe_event['type']}")

    # fetch necessary information to handle transaction
    checkout_info = stripe_event["data"]["object"]
    client_reference_id = checkout_info.get("client_reference_id")
    logger.info("Checkout Info (type): \n\n" + str(type(checkout_info)))
    logger.info("Checkout Info: \n\n" + str(checkout_info))
    logger.info("Checkout Info (keys): \n\n" + str(checkout_info.keys()))
    payment_link_id = checkout_info.get("payment_link")
    if payment_link_id is None:
        raise ValueError("No payment link found in checkout info")
    order = uow.orders.get_one(client_reference_id)
    credits_bought = _get_credits_bought(payment_link_id)

    # update user's number of credits
    user = uow.users.get_one(order.user_id)
    user.num_letter_credits += credits_bought
    user = uow.users.update(user)
    logger.info(f"Payment received for {credits_bought} credit(s) by user: {user}")

    # get original message - we don't know what the platform is, so we need to check first and retrieve a second time
    # this could/should be edited in the uow repository but this is the only occurrence in the codebase so far.
    og_message_base = uow.messages.get_one(order.message_id)
    if og_message_base.messaging_platform == "WhatsApp":
        og_message: t.Union[
            m.WhatsappMessage, m.TelegramMessage
        ] = uow.wa_messages.get_one(order.message_id)
    elif og_message_base.messaging_platform == "Telegram":
        og_message = uow.tg_messages.get_one(order.message_id)
    else:
        raise ValueError(
            f"Unsupported message platform: {og_message_base.messaging_platform}"
        )

    # dispatch letter
    was_dispatched = order.dispatch(uow)

    if was_dispatched:
        user.num_letter_credits -= 1
        user = uow.users.update(user)
    # return the messaging platform of the original request and the number of credits
    return was_dispatched, og_message, credits_bought, user.num_letter_credits


def _get_credits_bought(payment_link_id: str) -> int:
    """
    Retrieves the number of credits bought through a payment link.

    Args:
        payment_link_id (str): The payment link ID from which to retrieve the credits bought.

    Returns:
        int: The total number of credits bought.
    """
    logger.info("Payment link used to retrieve credits: " + payment_link_id)
    items_bought = stripe.PaymentLink.list_line_items(payment_link_id)["data"]
    total_credits = 0
    for item in items_bought:
        item_dict = t.cast(dict[str, t.Any], item)
        product_id = item_dict["price"]["product"]
        product = stripe.Product.retrieve(product_id)
        letter_credits = product["metadata"]["letter_credits"]
        total_credits += int(letter_credits)
    return total_credits


if __name__ == "__main__":
    plink = "plink_1Oo9zHLuDIWxSZxaQAbFlPrQ"
    print(_get_credits_bought(plink))

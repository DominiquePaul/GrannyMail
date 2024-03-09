import typing as t
import stripe
from grannymail.logger import logger
import grannymail.domain.models as m
import grannymail.config as cfg
import grannymail.integrations.pingen as pingen
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


def handle_event(stripe_event: dict, uow: AbstractUnitOfWork) -> tuple[str, m.Message]:
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

    checkout_info = stripe_event["data"]["object"]
    client_reference_id = checkout_info.get("client_reference_id")
    payment_link_id = checkout_info.get("payment_link_id")

    order = uow.orders.maybe_get_one(client_reference_id)
    original_message = uow.messages.maybe_get_one(client_reference_id)

    if order and original_message:
        raise ValueError(f"Order and User found for same ID: {client_reference_id}")
    elif order:
        return _handle_order_payment(order, uow)
    elif original_message:
        return _handle_credit_purchase(payment_link_id, original_message, uow)
    else:
        raise ValueError(f"No order or user found for ID: {client_reference_id}")


def _handle_order_payment(
    order: m.Order, uow: AbstractUnitOfWork
) -> tuple[str, m.Message]:
    """
    Processes the payment for an order.

    Args:
        order: The order for which the payment is processed.
        client_reference_id (str): The client reference ID associated with the order.
        uow (AbstractUnitOfWork): The unit of work abstraction to manage database transactions.

    Returns:
        tuple[str, m.Message]: A tuple containing the type of payment and the original message related to the payment.
    """
    order.dispatch(uow)
    original_message = uow.messages.get(order.message_id)
    user = uow.users.get(order.user_id)
    logger.info(f"Payment received for letter_payment by user: {user}")
    return "letter_payment", original_message


def _handle_credit_purchase(
    payment_link_id, original_message, uow
) -> tuple[str, m.Message]:
    """
    Processes the purchase of credits.

    Args:
        payment_link_id (str): The payment link ID associated with the credit purchase.
        original_message: The original message related to the credit purchase.
        uow (AbstractUnitOfWork): The unit of work abstraction to manage database transactions.

    Returns:
        tuple[str, m.Message]: A tuple containing the type of purchase and the original message related to the purchase.

    Raises:
        ValueError: If the payment link ID is missing.
    """
    if not payment_link_id:
        raise ValueError("Payment link ID is missing for credit purchase.")
    num_credits = _get_credits_bought(payment_link_id)
    user = uow.users.get(original_message.user_id)
    user.num_letter_credits += num_credits
    user = uow.users.update(user)
    item = f"{num_credits}_credit_purchase"
    logger.info(f"Payment received for {item} by user: {user}")
    return item, original_message


def _get_credits_bought(payment_link_id: str) -> int:
    """
    Retrieves the number of credits bought through a payment link.

    Args:
        payment_link_id (str): The payment link ID from which to retrieve the credits bought.

    Returns:
        int: The total number of credits bought.
    """
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

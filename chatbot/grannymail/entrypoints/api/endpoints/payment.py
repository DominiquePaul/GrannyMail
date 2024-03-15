import stripe
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

import grannymail.config as cfg
import grannymail.domain.models as m
import grannymail.integrations.stripe_payments as sp
from grannymail.integrations.messengers import telegram, whatsapp
from grannymail.logger import logger
from grannymail.services.unit_of_work import SupabaseUnitOfWork

router = APIRouter()


async def process_stripe_event(event, uow):
    """
    Processes a Stripe event, handling different types of payments.

    Args:
        event: The Stripe event to process.
        uow: The unit of work instance for database transactions.

    Raises:
        ValueError: If the item processed is not recognized.
    """
    was_dispatched, ref_message, credits_bought, user_credits = sp.handle_event(
        event, uow
    )

    # fetch the response content for the user
    if was_dispatched:
        msg_id = "stripe_webhook-success"
    else:
        msg_id = "stripe_webhook-success-no_dispatch"
    msg = uow.system_messages.get_msg(msg_id).format(credits_bought, user_credits)

    # Determine the messenger so we reply on the platform on which we got the message
    platform = ref_message.messaging_platform
    if isinstance(ref_message, m.WhatsappMessage):
        messenger = whatsapp.Whatsapp()
        await messenger.reply_text(ref_message, msg, uow)
    elif isinstance(ref_message, m.TelegramMessage):
        messenger = telegram.Telegram()
        await messenger.reply_text(ref_message, msg, uow)
    else:
        raise ValueError(f"Message platform {platform} not found")


@router.post("/stripe_webhook")
async def webhook(request: Request):
    """
    Endpoint to handle Stripe webhook events.

    Args:
        request: The request object containing the webhook payload and headers.

    Returns:
        JSONResponse: A response indicating the webhook was received.

    Raises:
        HTTPException: For various errors such as signature verification failure or unexpected errors.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, cfg.STRIPE_ENDPOINT_SECRET
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except stripe.error.SignatureVerificationError as e:  # type: ignore
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error handling Stripe event: {e}")
        raise HTTPException(
            status_code=500, detail="An error occurred while processing the event."
        )

    logger.info(f"Stripe webhook: Received event: {event['type']}")

    try:
        with SupabaseUnitOfWork() as uow:
            await process_stripe_event(event, uow)
            uow.commit()
    except ValueError as e:
        logger.error(f"Error processing Stripe event: {e}")
        raise HTTPException(
            status_code=500, detail="An error occurred while processing the event."
        )

    return JSONResponse(content={"message": "Webhook received!"}, status_code=200)

    return JSONResponse(content={"message": "Webhook received!"}, status_code=200)

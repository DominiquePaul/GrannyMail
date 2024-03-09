import stripe
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

import grannymail.config as cfg
from grannymail.logger import logger
import grannymail.integrations.stripe_payments as sp
from grannymail.services.unit_of_work import SupabaseUnitOfWork
from grannymail.services.message_processing_service import MessageProcessingService

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
    item, ref_message = sp.handle_event(event, uow)
    if item not in ["letter_payment", "5_credit_purchase", "10_credit_purchase"]:
        raise ValueError(f"Item {item} not found. Cannot reply")

    credits = item.split("_")[0] if "credit_purchase" in item else ""
    msg_key = "credit_purchase" if "credit_purchase" in item else item
    msg = uow.system_messages.get_msg(msg_key).format(credits)

    await MessageProcessingService()._get_messenger(
        ref_message.messaging_platform
    ).reply_text(ref_message, msg, uow)


@router.post("/stripe_webhook/")
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

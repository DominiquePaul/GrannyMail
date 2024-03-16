from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import grannymail.integrations.messengers.whatsapp as whatsapp
from grannymail.integrations.messengers.whatsapp import WebhookRequestData
from grannymail.logger import logger
from grannymail.services.message_processing_service import MessageProcessingService
from grannymail.services.unit_of_work import SupabaseUnitOfWork

router = APIRouter()


@router.get("/", status_code=200)
async def verify_route(request: Request):
    return whatsapp.fastapi_verify(request)


@router.post("/", status_code=200)
async def webhook_route(data: WebhookRequestData):
    if data.entry[0].get("changes", [{}])[0].get("value", {}).get("statuses"):
        logger.info("WA status update")
        return JSONResponse(content="ok")
    else:
        try:
            with SupabaseUnitOfWork() as uow:
                messenger = whatsapp.Whatsapp()
                await MessageProcessingService().receive_and_process_message(
                    uow, data=data, messenger=messenger
                )
                logger.info("Successfully handled query")
            return JSONResponse(content="ok")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            return JSONResponse(content="Internal Server Error", status_code=500)

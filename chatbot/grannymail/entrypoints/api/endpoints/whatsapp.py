from fastapi.responses import JSONResponse
from fastapi import APIRouter, Request

import grannymail.integrations.messengers.whatsapp as whatsapp
from grannymail.integrations.messengers.whatsapp import WebhookRequestData
from grannymail.services.message_processing_service import MessageProcessingService
from grannymail.logger import logger
from grannymail.services.unit_of_work import SupabaseUnitOfWork


router = APIRouter()


@router.get("/")
async def verify_route(request: Request):
    return whatsapp.fastapi_verify(request)


@router.post("/")
async def webhook_route(data: WebhookRequestData):
    if data.entry[0].get("changes", [{}])[0].get("value", {}).get("statuses"):
        logger.info("WA status update")
        return JSONResponse(content="ok", status_code=200)
    else:
        try:
            with SupabaseUnitOfWork() as uow:
                await MessageProcessingService().receive_and_process_message(
                    uow, data=data
                )
                logger.info("Successfully handled query")
            return JSONResponse(content="ok", status_code=200)
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            return JSONResponse(content="Internal Server Error", status_code=500)

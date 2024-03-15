import sentry_sdk
from fastapi import FastAPI

import grannymail.config as cfg

from .endpoints import payment, telegram, whatsapp

# setup sentry
if cfg.SENTRY_ENDPOINT:
    sentry_sdk.init(
        dsn=cfg.SENTRY_ENDPOINT,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        traces_sample_rate=1.0,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions.
        # We recommend adjusting this value in production.
        profiles_sample_rate=1.0,
    )


app = FastAPI(title="GrannyMail", lifespan=telegram.lifespan)

# Include routers from your endpoints
app.include_router(whatsapp.router, prefix="/api/whatsapp", tags=["whatsapp"])
app.include_router(telegram.router, prefix="/api/telegram", tags=["telegram"])
app.include_router(payment.router, prefix="/api/payment", tags=["payment"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "grannymail.entrypoints.fastapi:app", host="127.0.0.1", port=8000, reload=True
    )

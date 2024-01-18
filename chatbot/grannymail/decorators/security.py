from functools import wraps
import grannymail.config as cfg
import logging
import hashlib
import hmac

from fastapi import Request
from fastapi.responses import JSONResponse


def validate_signature(payload, signature):
    """
    Validate the incoming payload's signature against our expected signature
    """
    # Use the App Secret to hash the payload
    expected_signature = hmac.new(
        bytes(cfg.APP_SECRET, "latin-1"),
        msg=payload.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Check if the signature matches
    return hmac.compare_digest(expected_signature, signature)


def signature_required(f):
    """
    Decorator to ensure that the incoming requests to our webhook are valid and signed with the correct signature.
    """

    @wraps(f)
    async def decorated_function(request: Request, *args, **kwargs):
        body = await request.body()
        signature = request.headers.get(
            "X-Hub-Signature-256", "")[7:]  # Removing 'sha256='
        if not validate_signature(body.decode("utf-8"), signature):
            logging.info("Signature verification failed!")
            return JSONResponse(content={"status": "error", "message": "Invalid signature"}, status_code=403)
        return await f(*args, **kwargs)

    return decorated_function

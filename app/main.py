"""Realms Email Worker.

A standalone off-chain service that sends outbound email for Realms GOS realms.
Resend is the recommended provider; SMTP is supported as a fallback. All
secrets live in environment variables, never in the realm canister.

Endpoints:
  POST /send-email        - Send a single email immediately.
  POST /webhooks/resend   - Resend bounce/complaint/delivery webhooks.
  GET  /health            - Health check.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.email_bounce import handle_resend_webhook
from app.email_worker import start_email_worker
from app.email_sender import send_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


class SendEmailRequest(BaseModel):
    to: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject")
    text: str = Field(..., description="Plain text body")
    html: str = Field("", description="Optional HTML body")
    from_name: str = Field("", description="Display name for the From header")
    from_address: str = Field("", description="From email address")
    reply_to: str = Field("", description="Reply-To address")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Realms Email Worker")
    start_email_worker()
    yield
    logger.info("Shutting down Realms Email Worker")


app = FastAPI(
    title="Realms Email Worker",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
@app.get("/status")
async def health():
    return {"status": "healthy", "service": "realms-email-worker"}


@app.post("/send-email")
async def send_email_endpoint(payload: SendEmailRequest) -> Dict[str, Any]:
    """Send a single email immediately."""
    try:
        result = send_email(
            to=payload.to,
            subject=payload.subject,
            text=payload.text,
            html=payload.html,
            from_name=payload.from_name,
            from_address=payload.from_address,
            reply_to=payload.reply_to,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error sending email")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/webhooks/resend")
async def resend_webhook(request: Request) -> Dict[str, Any]:
    """Receive Resend bounce/complaint/delivery events."""
    try:
        payload = await request.json()
        await handle_resend_webhook(payload)
        return {"success": True}
    except Exception as exc:
        logger.exception("Error handling Resend webhook")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

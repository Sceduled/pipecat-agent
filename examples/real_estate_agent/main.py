"""
Prestige Realty — Voice Agent Server

Endpoints:
  GET  /health                  → health check
  GET  /voice-xml/inbound       → VoiceXML for Vobiz inbound DID webhook
  GET  /voice-xml/outbound      → VoiceXML for Vobiz outbound stream URL
  WS   /ws/inbound              → inbound call pipeline
  WS   /ws/outbound?session=X   → outbound call pipeline (session carries lead context)
  POST /dial                    → trigger an outbound call

Running locally (with ngrok):
  uvicorn main:app --port 8080 --reload
  ngrok http 8080
  Point Vobiz inbound DID webhook → https://<ngrok-url>/voice-xml/inbound

Deploying to Railway:
  railway up
  Set env vars in Railway dashboard
  Point Vobiz inbound DID webhook → https://<railway-url>/voice-xml/inbound
"""

import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request, WebSocket
from fastapi.responses import PlainTextResponse
from loguru import logger

from pipecat.serializers.vobiz import VobizFrameSerializer
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from inbound_agent import run_inbound
from outbound_agent import dial_lead, run_outbound

load_dotenv(Path(__file__).parent / ".env", override=True)

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------

DEEPGRAM_API_KEY = os.environ["DEEPGRAM_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
SARVAM_API_KEY = os.environ["SARVAM_API_KEY"]
VOBIZ_AUTH_ID = os.environ["VOBIZ_AUTH_ID"]           # X-Auth-ID from console.vobiz.ai
VOBIZ_AUTH_TOKEN = os.environ["VOBIZ_AUTH_TOKEN"]     # X-Auth-Token from console.vobiz.ai
VOBIZ_FROM_NUMBER = os.environ["VOBIZ_PHONE_NUMBER"]   # Your Vobiz DID
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")  # e.g. https://xxxx.up.railway.app

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Prestige Realty Voice Agent starting")
    yield
    logger.info("Prestige Realty Voice Agent stopped")


app = FastAPI(title="Prestige Realty Voice Agent", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# VoiceXML — tells Vobiz to open a WebSocket stream to your server
# ---------------------------------------------------------------------------


@app.api_route("/voice-xml/inbound", methods=["GET", "POST"], response_class=PlainTextResponse)
async def voice_xml_inbound(request: Request):
    """
    Set this URL as your Vobiz DID webhook for inbound calls.
    Vobiz fetches this when a customer dials your number.
    """
    ws_url = _ws_base_url(request) + "/ws/inbound"
    return PlainTextResponse(
        content=_stream_xml(ws_url),
        media_type="text/xml",
    )


@app.api_route("/voice-xml/outbound", methods=["GET", "POST"], response_class=PlainTextResponse)
async def voice_xml_outbound(request: Request, session: str = Query(...)):
    """
    Vobiz fetches this URL to get the stream directive for an outbound call.
    The session token is passed as a query param so the WebSocket handler
    can look up the lead context.
    """
    ws_url = _ws_base_url(request) + f"/ws/outbound?session={session}"
    return PlainTextResponse(
        content=_stream_xml(ws_url),
        media_type="text/xml",
    )


# ---------------------------------------------------------------------------
# WebSocket handlers
# ---------------------------------------------------------------------------


@app.websocket("/ws/inbound")
async def ws_inbound(websocket: WebSocket):
    """Handles every inbound call from Vobiz."""
    await websocket.accept()
    logger.info("Inbound WebSocket accepted")
    try:
        transport = _make_transport(websocket)
        await run_inbound(
            transport=transport,
            deepgram_api_key=DEEPGRAM_API_KEY,
            openai_api_key=OPENAI_API_KEY,
            sarvam_api_key=SARVAM_API_KEY,
        )
    except Exception as e:
        logger.exception(f"Inbound call pipeline error: {e}")


@app.websocket("/ws/outbound")
async def ws_outbound(websocket: WebSocket, session: str = Query(...)):
    """Handles every outbound call from Vobiz. session carries the lead context."""
    await websocket.accept()
    logger.info(f"Outbound WebSocket accepted for session={session}")
    try:
        transport = _make_transport(websocket)
        await run_outbound(
            transport=transport,
            session_token=session,
            deepgram_api_key=DEEPGRAM_API_KEY,
            openai_api_key=OPENAI_API_KEY,
            sarvam_api_key=SARVAM_API_KEY,
        )
    except Exception as e:
        logger.exception(f"Outbound call pipeline error: {e}")


# ---------------------------------------------------------------------------
# Outbound dial trigger
# ---------------------------------------------------------------------------


@app.post("/dial")
async def dial(request: Request):
    """
    Trigger an outbound call to a lead.

    Request body:
        {
            "to": "+919876543210",          required
            "name": "Rahul Sharma",         required
            "call_type": "follow_up",       follow_up | visit_reminder | new_launch
            "interest": "3BHK in Whitefield under 90L",
            "visit_date": "2026-06-25",     for visit_reminder
            "visit_time": "11:00 AM",       for visit_reminder
            "property_name": "Prestige Tech Vista"
        }
    """
    body = await request.json()

    to_number = body.get("to")
    if not to_number:
        return {"error": "'to' field is required"}

    lead_context = {
        "name": body.get("name", ""),
        "call_type": body.get("call_type", "follow_up"),
        "interest": body.get("interest", ""),
        "visit_date": body.get("visit_date", ""),
        "visit_time": body.get("visit_time", ""),
        "property_name": body.get("property_name", ""),
        "phone": to_number,
    }

    from outbound_agent import pending_outbound_sessions
    session_token = str(uuid.uuid4())
    pending_outbound_sessions[session_token] = lead_context

    base = PUBLIC_URL if PUBLIC_URL else _http_base_url(request)
    answer_url = f"{base}/voice-xml/outbound?session={session_token}"

    result = await dial_lead(
        to_number=to_number,
        from_number=VOBIZ_FROM_NUMBER,
        vobiz_auth_id=VOBIZ_AUTH_ID,
        vobiz_auth_token=VOBIZ_AUTH_TOKEN,
        answer_url=answer_url,
    )
    return {"status": "dialing", "to": to_number, "session": session_token, "vobiz": result}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_transport(websocket: WebSocket) -> FastAPIWebsocketTransport:
    """Create a Vobiz WebSocket transport for a call.

    VAD is intentionally NOT set here. VAD lives only inside the aggregator
    (LLMUserAggregatorParams.vad_analyzer). Running VAD at both the transport
    and aggregator levels causes the aggregator to go deaf after the opening
    greeting because the two VAD instances emit conflicting turn frames.
    """
    return FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=VobizFrameSerializer(),
        ),
    )


def _http_base_url(request: Request) -> str:
    """Return https:// or http:// base URL, respecting reverse-proxy headers."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    scheme = "https" if proto in ("https", "wss") else "http"
    return f"{scheme}://{request.headers.get('host', 'localhost')}"


def _ws_base_url(request: Request) -> str:
    """Return wss:// or ws:// base URL, respecting reverse-proxy headers."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    scheme = "wss" if proto in ("https", "wss") else "ws"
    return f"{scheme}://{request.headers.get('host', 'localhost')}"


def _stream_xml(ws_url: str) -> str:
    """Return a Vobiz VoiceXML Stream directive pointing to the given WebSocket URL."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Stream bidirectional="true" keepCallAlive="true" contentType="audio/x-mulaw;rate=8000">{ws_url}</Stream>
</Response>"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

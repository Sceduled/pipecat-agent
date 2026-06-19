"""
Real Estate Voice Agent — Vobiz + Deepgram STT + Groq/OpenAI LLM + Sarvam TTS

Inbound call flow:
  Caller dials your Vobiz DID
  → Vobiz fetches your /voice-xml endpoint (returns Stream directive)
  → Vobiz opens WebSocket to /ws/call
  → Pipeline: Deepgram STT → Groq LLM → Sarvam TTS → caller's ear

Outbound call flow:
  POST /dial  {"to": "+91...", "agent_context": {...}}
  → Vobiz REST API dials the number
  → Vobiz opens WebSocket to /ws/call (same pipeline)

Deploy to Railway:
  railway up
  Set env vars in Railway dashboard (see .env.example)
  Point Vobiz webhook to https://<your-app>.railway.app/voice-xml

Usage (local dev with ngrok):
  uvicorn voice-vobiz-realestate:app --port 8080
  ngrok http 8080
  Set Vobiz DID webhook to https://<ngrok>.ngrok.io/voice-xml
"""

import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime

import aiohttp
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import PlainTextResponse
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import EndFrame, LLMMessagesFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.serializers.vobiz import VobizFrameSerializer
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.workers.runner import WorkerRunner

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are Priya, a friendly and professional AI assistant for
Prestige Realty. Your job is to help callers find their perfect home or
investment property.

Your goals in order:
1. Greet the caller warmly and ask how you can help.
2. Understand their requirement: buy/rent/invest, location preference,
   budget range, BHK preference, and timeline.
3. Match them to available properties from the catalog (use search_properties).
4. Offer to schedule a site visit (use book_site_visit).
5. Save the lead to CRM (use save_lead) once you have name + phone.
6. If they ask about EMI, use calculate_emi.
7. If they want to speak to a human agent, use transfer_to_agent.

Rules:
- Keep responses short — this is a phone call.
- Speak in the caller's language (Hindi/English mix is fine).
- Never make up property details. Only quote what search_properties returns.
- If you don't know something, say "Let me check and call you back."
"""

# ---------------------------------------------------------------------------
# Tool functions (register with LLM)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_properties",
            "description": "Search available properties by budget, location, and BHK.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "Area or city, e.g. Whitefield"},
                    "budget_lakhs": {"type": "number", "description": "Max budget in lakhs INR"},
                    "bhk": {"type": "integer", "description": "Number of bedrooms (1, 2, 3, 4)"},
                    "purpose": {
                        "type": "string",
                        "enum": ["buy", "rent", "invest"],
                        "description": "Purpose of purchase",
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_site_visit",
            "description": "Book a site visit for a property.",
            "parameters": {
                "type": "object",
                "properties": {
                    "caller_name": {"type": "string"},
                    "caller_phone": {"type": "string"},
                    "property_id": {"type": "string"},
                    "preferred_date": {"type": "string", "description": "e.g. 2026-06-20"},
                    "preferred_time": {"type": "string", "description": "e.g. 11:00 AM"},
                },
                "required": ["caller_name", "caller_phone", "property_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_lead",
            "description": "Save caller details to CRM.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "budget_lakhs": {"type": "number"},
                    "location": {"type": "string"},
                    "bhk": {"type": "integer"},
                    "purpose": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["name", "phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_emi",
            "description": "Calculate monthly EMI for a property.",
            "parameters": {
                "type": "object",
                "properties": {
                    "price_lakhs": {"type": "number"},
                    "down_payment_percent": {"type": "number", "default": 20},
                    "interest_rate": {"type": "number", "default": 8.5},
                    "tenure_years": {"type": "integer", "default": 20},
                },
                "required": ["price_lakhs"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_to_agent",
            "description": "Transfer the caller to a human sales agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                },
                "required": [],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def handle_tool_call(tool_name: str, tool_args: dict) -> str:
    """Route LLM tool calls to real implementations."""

    if tool_name == "search_properties":
        # TODO: replace with your real property DB query
        return json.dumps(
            [
                {
                    "id": "PRES-WF-001",
                    "name": "Prestige Lakeside Habitat",
                    "location": tool_args.get("location", "Whitefield"),
                    "bhk": tool_args.get("bhk", 3),
                    "price_lakhs": 85,
                    "possession": "Dec 2026",
                    "highlights": "Clubhouse, pool, 24x7 security",
                },
                {
                    "id": "PRES-WF-002",
                    "name": "Prestige Tech Vista",
                    "location": tool_args.get("location", "Whitefield"),
                    "bhk": tool_args.get("bhk", 2),
                    "price_lakhs": 62,
                    "possession": "Ready to move",
                    "highlights": "Gym, co-working space, metro nearby",
                },
            ]
        )

    if tool_name == "book_site_visit":
        # TODO: integrate with Google Calendar or your CRM
        logger.info(f"Site visit booked: {tool_args}")
        return json.dumps(
            {
                "status": "confirmed",
                "confirmation_id": "SV-2026-" + datetime.now().strftime("%H%M%S"),
                "message": f"Site visit booked for {tool_args.get('preferred_date', 'the requested date')} at {tool_args.get('preferred_time', '10:00 AM')}",
            }
        )

    if tool_name == "save_lead":
        # TODO: POST to your CRM (HubSpot, Zoho, Salesforce, etc.)
        logger.info(f"Lead saved: {tool_args}")
        return json.dumps({"status": "saved", "lead_id": "LEAD-" + datetime.now().strftime("%Y%m%d%H%M%S")})

    if tool_name == "calculate_emi":
        price = tool_args["price_lakhs"] * 100_000
        down = tool_args.get("down_payment_percent", 20) / 100
        rate = tool_args.get("interest_rate", 8.5) / 100 / 12
        months = tool_args.get("tenure_years", 20) * 12
        principal = price * (1 - down)
        if rate == 0:
            emi = principal / months
        else:
            emi = principal * rate * (1 + rate) ** months / ((1 + rate) ** months - 1)
        return json.dumps(
            {
                "loan_amount_lakhs": round(principal / 100_000, 2),
                "emi_per_month": round(emi),
                "total_interest_lakhs": round((emi * months - principal) / 100_000, 2),
            }
        )

    if tool_name == "transfer_to_agent":
        logger.info(f"Transferring to human agent: {tool_args.get('reason', '')}")
        return json.dumps({"status": "transferring", "message": "Connecting you to an agent now."})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


# ---------------------------------------------------------------------------
# Pipeline factory
# ---------------------------------------------------------------------------

def build_pipeline(transport: FastAPIWebsocketTransport, is_outbound: bool = False, lead_context: dict | None = None):
    """Build and return the voice pipeline for a single call."""

    # --- STT ---
    stt = DeepgramSTTService(
        api_key=os.environ["DEEPGRAM_API_KEY"],
        # language="hi" for Hindi-only calls
    )

    # --- LLM ---
    # Use Groq for lower latency; swap to OpenAI for better quality
    use_groq = os.environ.get("USE_GROQ", "true").lower() == "true"
    if use_groq:
        llm = GroqLLMService(
            api_key=os.environ["GROQ_API_KEY"],
            model="llama-3.3-70b-versatile",
        )
    else:
        llm = OpenAILLMService(
            api_key=os.environ["OPENAI_API_KEY"],
            model="gpt-4o-mini",
        )

    # --- TTS ---
    tts = SarvamTTSService(
        api_key=os.environ["SARVAM_API_KEY"],
        voice_id=os.environ.get("SARVAM_VOICE", "anushka"),
        model=os.environ.get("SARVAM_MODEL", "bulbul:v3"),
    )

    # --- Context ---
    system_message = SYSTEM_PROMPT
    messages = [{"role": "system", "content": system_message}]

    if is_outbound and lead_context:
        # Pre-fill context for outbound calls (we know who we're calling)
        messages.append(
            {
                "role": "system",
                "content": (
                    f"You are calling {lead_context.get('name', 'the customer')} "
                    f"at {lead_context.get('phone', '')}. "
                    f"They previously enquired about {lead_context.get('interest', 'properties')}. "
                    "Introduce yourself first and ask how they're doing."
                ),
            }
        )

    context = OpenAILLMContext(messages=messages, tools=TOOLS)
    context_aggregator = llm.create_context_aggregator(context)

    # Wire tool call results back into LLM context
    llm.register_function(None, handle_tool_call)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )
    return pipeline


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Real Estate Voice Agent starting up")
    yield
    logger.info("Real Estate Voice Agent shutting down")


app = FastAPI(title="Prestige Realty Voice Agent", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "prestige-realty-voice-agent"}


@app.get("/voice-xml", response_class=PlainTextResponse)
async def voice_xml(request: Request):
    """
    Vobiz fetches this URL when a call comes in.
    Returns VoiceXML that instructs Vobiz to open a WebSocket stream to /ws/call.

    Point your Vobiz DID webhook to: https://<your-domain>/voice-xml
    """
    host = request.headers.get("host", "localhost")
    scheme = "wss" if request.url.scheme == "https" else "ws"
    ws_url = f"{scheme}://{host}/ws/call"

    # Vobiz VoiceXML Stream directive
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}"/>
    </Connect>
</Response>"""
    return PlainTextResponse(content=xml, media_type="text/xml")


@app.websocket("/ws/call")
async def websocket_call(websocket: WebSocket):
    """Main WebSocket endpoint — handles both inbound and outbound calls."""

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.8)),
            serializer=VobizFrameSerializer(),  # auto-populates StreamSid from start event
        ),
    )

    pipeline = build_pipeline(transport)
    worker = PipelineWorker(pipeline)
    runner = WorkerRunner()
    await runner.add_workers(worker)
    await runner.run()


@app.post("/dial")
async def dial_outbound(request: Request):
    """
    Trigger an outbound call via Vobiz REST API.

    Body:
        {
            "to": "+919876543210",
            "name": "Rahul Sharma",
            "interest": "3BHK in Whitefield under 90 lakhs"
        }
    """
    body = await request.json()
    to_number = body.get("to")
    if not to_number:
        return {"error": "to field is required"}

    vobiz_api_key = os.environ["VOBIZ_API_KEY"]
    vobiz_from_number = os.environ["VOBIZ_FROM_NUMBER"]
    host = request.headers.get("host", "localhost")
    scheme = request.url.scheme
    ws_url = f"{'wss' if scheme == 'https' else 'ws'}://{host}/ws/call"

    # Vobiz outbound call API (check docs.vobiz.ai for exact endpoint)
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.vobiz.ai/v1/calls",
            headers={"Authorization": f"Bearer {vobiz_api_key}", "Content-Type": "application/json"},
            json={
                "to": to_number,
                "from": vobiz_from_number,
                "stream_url": ws_url,
                "stream_bidirectional": True,
            },
        ) as resp:
            result = await resp.json()
            logger.info(f"Outbound call initiated: {result}")
            return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

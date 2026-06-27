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

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request, WebSocket
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from pipecat.serializers.vobiz import VobizFrameSerializer
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from inbound_agent import run_inbound
from outbound_agent import dial_lead, run_outbound
from multilingual_outbound_agent import run_multilingual_outbound

load_dotenv(Path(__file__).parent / ".env", override=True)

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------

DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")
VOBIZ_AUTH_ID = os.environ.get("VOBIZ_AUTH_ID", "")           # X-Auth-ID from console.vobiz.ai
VOBIZ_AUTH_TOKEN = os.environ.get("VOBIZ_AUTH_TOKEN", "")     # X-Auth-Token from console.vobiz.ai
VOBIZ_FROM_NUMBER = os.environ.get("VOBIZ_PHONE_NUMBER", "")   # Your Vobiz DID
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")  # e.g. https://xxxx.up.railway.app

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if OPENAI_API_KEY:
        logger.info(f"LLM: OpenAI gpt-4o-mini (key ends ...{OPENAI_API_KEY[-4:]})")
    else:
        logger.critical("OPENAI_API_KEY is not set — all calls will be silent!")
    logger.info("Prestige Realty Voice Agent starting")
    yield
    logger.info("Prestige Realty Voice Agent stopped")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    to_number = request.query_params.get("To")
    if not to_number and request.method == "POST":
        form = await request.form()
        to_number = form.get("To")

    agent_id = ""
    if to_number:
        from database import SessionLocal, PhoneNumber
        db = SessionLocal()
        phone_record = db.query(PhoneNumber).filter(PhoneNumber.phone_number == to_number).first()
        if phone_record:
            agent_id = phone_record.agent_id
        db.close()

    ws_url = _ws_base_url(request) + f"/ws/inbound?agent_id={agent_id}"
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


@app.api_route("/voice-xml/outbound-multilingual", methods=["GET", "POST"], response_class=PlainTextResponse)
async def voice_xml_outbound_multilingual(request: Request, session: str = Query(...)):
    """
    Vobiz fetches this URL to get the stream directive for a multilingual outbound call.
    """
    ws_url = _ws_base_url(request) + f"/ws/outbound-multilingual?session={session}"
    return PlainTextResponse(
        content=_stream_xml(ws_url),
        media_type="text/xml",
    )


# ---------------------------------------------------------------------------
# WebSocket handlers
# ---------------------------------------------------------------------------


@app.websocket("/ws/inbound")
async def ws_inbound(websocket: WebSocket, agent_id: str = Query("")):
    """Handles every inbound call from Vobiz."""
    from database import SessionLocal, Agent as DBAgent, CallLog
    
    db = SessionLocal()
    agent = db.query(DBAgent).filter(DBAgent.id == agent_id).first()
    db.close()

    if not agent:
        logger.error(f"Agent {agent_id} not found in database for inbound call")
        await websocket.close(code=4004, reason="Invalid agent_id")
        return

    await websocket.accept()
    logger.info(f"Inbound WebSocket accepted for agent={agent.name}")
    
    # Log the call
    db = SessionLocal()
    call_log = CallLog(agent_id=agent_id, direction="inbound", caller_number="Inbound Caller")
    db.add(call_log)
    db.commit()
    db.close()
    
    try:
        transport = _make_transport(websocket)
        messages = await run_inbound(
            transport=transport,
            deepgram_api_key=DEEPGRAM_API_KEY,
            openai_api_key=OPENAI_API_KEY,
            sarvam_api_key=SARVAM_API_KEY,
            system_prompt=agent.system_prompt,
            voice=agent.voice,
            company_name=agent.company_name,
            knowledge_base=agent.knowledge_base,
            niche=agent.niche,
        )
        
        # Save transcript
        if messages:
            transcript = "\n".join([f"{msg['role'].capitalize()}: {msg.get('content', '')}" for msg in messages if msg.get("role") in ["user", "assistant"]])
            db = SessionLocal()
            db_log = db.query(CallLog).filter(CallLog.id == call_log.id).first()
            if db_log:
                db_log.transcript = transcript
                db.commit()
            db.close()
            
    except Exception as e:
        import traceback
        with open("crash.log", "a") as f:
            f.write("INBOUND ERROR:\n" + traceback.format_exc() + "\n")
        logger.exception(f"Inbound call pipeline error: {e}")


@app.websocket("/ws/outbound")
async def ws_outbound(websocket: WebSocket, session: str = Query(...)):
    """Handles every outbound call from Vobiz. session carries the lead context."""
    from database import SessionLocal, Agent as DBAgent, CallLog
    from outbound_agent import pending_outbound_sessions
    
    context = pending_outbound_sessions.get(session)
    if not context:
        logger.error(f"No session found for token {session}")
        await websocket.close(code=4004, reason="Invalid session")
        return

    agent_id = context.get("agent_id")
    if not agent_id:
        logger.error(f"No agent_id found for session {session}")
        await websocket.close(code=4004, reason="Invalid agent_id")
        return

    db = SessionLocal()
    agent = db.query(DBAgent).filter(DBAgent.id == agent_id).first()
    db.close()

    if not agent:
        logger.error(f"Agent {agent_id} not found in database")
        await websocket.close(code=4004, reason="Invalid agent_id")
        return

    await websocket.accept()
    logger.info(f"Outbound WebSocket accepted for session={session}, agent={agent.name}")

    lead_phone = context.get("phone", context.get("lead", {}).get("phone", "Unknown Lead"))

    # Write call log in background — does not block pipeline startup
    async def _log_call():
        db = SessionLocal()
        cl = CallLog(agent_id=agent_id, direction="outbound", caller_number=lead_phone)
        db.add(cl)
        db.commit()
        db.refresh(cl)
        cl_id = cl.id
        db.close()
        return cl_id

    log_task = asyncio.create_task(_log_call())

    try:
        transport = _make_transport(websocket)
        override_system_prompt = context.get("system_prompt")
        override_voice = context.get("voice")

        system_prompt = override_system_prompt if override_system_prompt else agent.system_prompt
        voice = override_voice if override_voice else agent.voice

        messages = await run_outbound(
            transport=transport,
            session_token=session,
            deepgram_api_key=DEEPGRAM_API_KEY,
            openai_api_key=OPENAI_API_KEY,
            sarvam_api_key=SARVAM_API_KEY,
            system_prompt=system_prompt,
            voice=voice,
            company_name=agent.company_name,
            knowledge_base=agent.knowledge_base,
            niche=agent.niche,
        )

        if messages:
            transcript = "\n".join([f"{msg['role'].capitalize()}: {msg.get('content', '')}" for msg in messages if msg.get("role") in ["user", "assistant"]])
            call_log_id = await log_task
            db = SessionLocal()
            db_log = db.query(CallLog).filter(CallLog.id == call_log_id).first()
            if db_log:
                db_log.transcript = transcript
                db.commit()
            db.close()
            
    except Exception as e:
        import traceback
        with open("crash.log", "a") as f:
            f.write("OUTBOUND ERROR:\n" + traceback.format_exc() + "\n")
        logger.exception(f"Outbound call pipeline error: {e}")


@app.websocket("/ws/outbound-multilingual")
async def ws_outbound_multilingual(websocket: WebSocket, session: str = Query(...)):
    """Handles every outbound multilingual call from Vobiz. session carries the lead context."""
    from database import SessionLocal, Agent as DBAgent, CallLog
    
    from multilingual_outbound_agent import pending_multilingual_sessions
    context = pending_multilingual_sessions.get(session)
    if not context:
        logger.error(f"No multilingual session found for token {session}")
        await websocket.close(code=4004, reason="Invalid session")
        return

    agent_id = context.get("agent_id")
    if not agent_id:
        logger.error(f"No agent_id found for session {session}")
        await websocket.close(code=4004, reason="Invalid agent_id")
        return

    db = SessionLocal()
    agent = db.query(DBAgent).filter(DBAgent.id == agent_id).first()
    db.close()

    if not agent:
        logger.error(f"Agent {agent_id} not found in database")
        await websocket.close(code=4004, reason="Invalid agent_id")
        return

    await websocket.accept()
    logger.info(f"Multilingual Outbound WebSocket accepted for session={session}, agent={agent.name}")

    lead_phone = context.get("phone", context.get("lead", {}).get("phone", "Unknown Lead"))

    # Write call log in background — does not block pipeline startup
    async def _log_call_ml():
        db = SessionLocal()
        cl = CallLog(agent_id=agent_id, direction="outbound-multilingual", caller_number=lead_phone)
        db.add(cl)
        db.commit()
        db.refresh(cl)
        cl_id = cl.id
        db.close()
        return cl_id

    log_task_ml = asyncio.create_task(_log_call_ml())

    try:
        transport = _make_transport(websocket)
        override_system_prompt = context.get("system_prompt")
        override_voice = context.get("voice")

        system_prompt = override_system_prompt if override_system_prompt else agent.system_prompt
        voice = override_voice if override_voice else agent.voice

        messages = await run_multilingual_outbound(
            transport=transport,
            session_token=session,
            deepgram_api_key=DEEPGRAM_API_KEY,
            openai_api_key=OPENAI_API_KEY,
            sarvam_api_key=SARVAM_API_KEY,
            system_prompt=system_prompt,
            voice=voice,
            company_name=agent.company_name,
            knowledge_base=agent.knowledge_base,
            niche=agent.niche,
        )

        if messages:
            transcript = "\n".join([f"{msg['role'].capitalize()}: {msg.get('content', '')}" for msg in messages if msg.get("role") in ["user", "assistant"]])
            call_log_id_ml = await log_task_ml
            db = SessionLocal()
            db_log = db.query(CallLog).filter(CallLog.id == call_log_id_ml).first()
            if db_log:
                db_log.transcript = transcript
                db.commit()
            db.close()
            
    except Exception as e:
        import traceback
        with open("crash.log", "a") as f:
            f.write("MULTILINGUAL OUTBOUND ERROR:\n" + traceback.format_exc() + "\n")
        logger.exception(f"Multilingual Outbound call pipeline error: {e}")


# ---------------------------------------------------------------------------
# Outbound dial trigger
# ---------------------------------------------------------------------------


@app.post("/dial")
async def dial(request: Request):
    """
    Trigger an outbound call to a lead.
    """
    body = await request.json()

    agent_id = body.get("agent_id")
    if not agent_id:
        return {"error": "'agent_id' field is required"}

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
        "agent_id": agent_id,
        "phone": to_number,
        "voice": body.get("voice"),
        "system_prompt": body.get("system_prompt")
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


@app.post("/dial-multilingual")
async def dial_multilingual(request: Request):
    """
    Trigger a multilingual outbound call to a lead.
    """
    body = await request.json()

    agent_id = body.get("agent_id")
    if not agent_id:
        return {"error": "'agent_id' field is required"}

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
        "agent_id": agent_id,
        "phone": to_number,
        "voice": body.get("voice"),
        "system_prompt": body.get("system_prompt")
    }

    from multilingual_outbound_agent import pending_multilingual_sessions
    session_token = str(uuid.uuid4())
    pending_multilingual_sessions[session_token] = lead_context

    base = PUBLIC_URL if PUBLIC_URL else _http_base_url(request)
    answer_url = f"{base}/voice-xml/outbound-multilingual?session={session_token}"

    result = await dial_lead(
        to_number=to_number,
        from_number=VOBIZ_FROM_NUMBER,
        vobiz_auth_id=VOBIZ_AUTH_ID,
        vobiz_auth_token=VOBIZ_AUTH_TOKEN,
        answer_url=answer_url,
    )

    return {"status": "dialing_multilingual", "to": to_number, "session": session_token, "vobiz": result}


# ---------------------------------------------------------------------------
# Agent APIs
# ---------------------------------------------------------------------------

from database import get_db, Agent as DBAgent, PhoneNumber, CallLog
from pydantic import BaseModel
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

class AgentCreate(BaseModel):
    name: str
    company_name: str = ""
    niche: str
    agent_type: str
    system_prompt: str
    voice: str
    knowledge_base: str = ""

class AgentUpdate(BaseModel):
    name: str
    company_name: str = ""
    niche: str
    agent_type: str
    system_prompt: str
    voice: str
    knowledge_base: str = ""

class PhoneCreate(BaseModel):
    phone_number: str

@app.get("/api/agents")
async def get_all_agents(db: Session = Depends(get_db)):
    agents = db.query(DBAgent).order_by(DBAgent.created_at.desc()).all()
    return agents

@app.get("/api/seed")
async def seed_agents(db: Session = Depends(get_db)):
    agents = [
        {"name": "Inbound Agent", "agent_type": "inbound", "niche": "real_estate", "voice": "priya", "prompt": "You are Priya, an inbound agent..."},
        {"name": "Outbound Agent", "agent_type": "outbound", "niche": "real_estate", "voice": "priya", "prompt": "You are Priya, an outbound agent..."},
        {"name": "Multilingual Agent", "agent_type": "multilingual_outbound", "niche": "real_estate", "voice": "priya", "prompt": "You are Priya, a multilingual agent..."}
    ]
    created = 0
    for a in agents:
        existing = db.query(DBAgent).filter(DBAgent.name == a["name"]).first()
        if not existing:
            db.add(DBAgent(name=a["name"], agent_type=a["agent_type"], niche=a["niche"], system_prompt=a["prompt"], voice=a["voice"]))
            created += 1
    db.commit()
    return {"message": f"Seeded {created} default agents."}

@app.get("/api/crash")
async def get_crash_log():
    try:
        with open("crash.log", "r") as f:
            return {"log": f.read()}
    except FileNotFoundError:
        return {"log": "No crashes recorded yet!"}

@app.get("/api/templates")
async def get_templates():
    return [
        {
            "id": "real_estate",
            "name": "Real Estate Agent",
            "description": "Qualify buyers, schedule property tours, and answer FAQs.",
            "prompt": "You are a warm and professional Real Estate Voice Assistant..."
        },
        {
            "id": "healthcare",
            "name": "Healthcare Clinic",
            "description": "Book appointments, answer clinic hours, and assist patients.",
            "prompt": "You are a helpful and empathetic Medical Receptionist. Your job is to assist patients with booking appointments, checking clinic hours, and answering general questions."
        },
        {
            "id": "recruitment",
            "name": "Recruitment Screener",
            "description": "Screen candidates, ask preliminary interview questions.",
            "prompt": "You are an AI Recruitment Screener. Your job is to call candidates, ask them a set of preliminary interview questions regarding their experience, and note down their responses."
        },
        {
            "id": "customer_support",
            "name": "Customer Support",
            "description": "Handle customer inquiries, refunds, and general support.",
            "prompt": "You are a polite and helpful Customer Support Agent. Your goal is to help customers resolve issues, process refunds, and answer FAQs about our products."
        },
        {
            "id": "custom",
            "name": "Custom Agent",
            "description": "Start from scratch and build your own custom voice AI.",
            "prompt": "You are a helpful AI assistant."
        }
    ]

@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(DBAgent).filter(DBAgent.id == agent_id).first()
    if not agent:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.post("/api/agents")
async def create_agent(agent: AgentCreate, db: Session = Depends(get_db)):
    db_agent = DBAgent(
        name=agent.name,
        company_name=agent.company_name,
        niche=agent.niche,
        agent_type=agent.agent_type,
        system_prompt=agent.system_prompt,
        voice=agent.voice,
        knowledge_base=agent.knowledge_base
    )
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.put("/api/agents/{agent_id}")
async def update_agent(agent_id: str, agent: AgentUpdate, db: Session = Depends(get_db)):
    db_agent = db.query(DBAgent).filter(DBAgent.id == agent_id).first()
    if not db_agent:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Agent not found")
    db_agent.name = agent.name
    db_agent.company_name = agent.company_name
    db_agent.niche = agent.niche
    db_agent.agent_type = agent.agent_type
    db_agent.system_prompt = agent.system_prompt
    db_agent.voice = agent.voice
    db_agent.knowledge_base = agent.knowledge_base
    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.post("/api/agents/{agent_id}/upload")
async def upload_knowledge(agent_id: str, request: Request, db: Session = Depends(get_db)):
    db_agent = db.query(DBAgent).filter(DBAgent.id == agent_id).first()
    if not db_agent:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Agent not found")
        
    form = await request.form()
    file = form.get("file")
    if not file:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="No file uploaded")
        
    import io
    content = await file.read()
    filename = file.filename.lower()
    extracted_text = ""
    
    if filename.endswith(".pdf"):
        import PyPDF2
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"
    else:
        # Fallback for plain text files
        extracted_text = content.decode("utf-8", errors="ignore")
        
    # Append the extracted text to the existing knowledge base
    existing_kb = db_agent.knowledge_base or ""
    new_kb = existing_kb + f"\n\n--- Document: {file.filename} ---\n{extracted_text}"
    db_agent.knowledge_base = new_kb.strip()
    db.commit()
    
    return {"message": f"Successfully parsed {file.filename} and added to knowledge base.", "text_preview": extracted_text[:200]}

@app.get("/api/agents/{agent_id}/phones")
async def get_agent_phones(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(DBAgent).filter(DBAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    phones = db.query(PhoneNumber).filter(PhoneNumber.agent_id == agent_id).all()
    return phones

@app.post("/api/agents/{agent_id}/phones")
async def add_agent_phone(agent_id: str, phone: PhoneCreate, db: Session = Depends(get_db)):
    agent = db.query(DBAgent).filter(DBAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Check if number already mapped
    existing = db.query(PhoneNumber).filter(PhoneNumber.phone_number == phone.phone_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Phone number already assigned")
        
    db_phone = PhoneNumber(phone_number=phone.phone_number, agent_id=agent_id)
    db.add(db_phone)
    db.commit()
    db.refresh(db_phone)
    return db_phone

@app.delete("/api/agents/{agent_id}/phones/{phone_number}")
async def remove_agent_phone(agent_id: str, phone_number: str, db: Session = Depends(get_db)):
    db_phone = db.query(PhoneNumber).filter(PhoneNumber.phone_number == phone_number, PhoneNumber.agent_id == agent_id).first()
    if not db_phone:
        raise HTTPException(status_code=404, detail="Phone number mapping not found")
    db.delete(db_phone)
    db.commit()
    return {"status": "deleted"}

@app.get("/api/agents/{agent_id}/logs")
async def get_agent_logs(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(DBAgent).filter(DBAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    logs = db.query(CallLog).filter(CallLog.agent_id == agent_id).order_by(CallLog.created_at.desc()).all()
    return logs



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

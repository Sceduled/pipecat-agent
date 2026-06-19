"""
Outbound Call Agent — Prestige Realty

Triggered by a POST to /dial with the lead's details.
Server stores the lead context in memory keyed by a session token,
calls the Vobiz REST API to dial the lead,
Vobiz opens a WebSocket to /ws/outbound?session=<token>,
and the pipeline picks up the pre-stored lead context.
"""

import aiohttp
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import (
    SpeechTimeoutUserTurnStopStrategy,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport
from pipecat.workers.runner import WorkerRunner

from tools import OUTBOUND_TOOLS

# ---------------------------------------------------------------------------
# Session store
# ---------------------------------------------------------------------------

pending_outbound_sessions: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_BASE_RULES = """
PHONE CALL SPEAKING RULES — follow these exactly:
- Speak in 1 to 3 complete, naturally connected sentences per response.
- Use smooth connectors that create natural flow: "So, what I can do is...", "That's great — just to confirm...", "Perfect, let me grab those details."
- Never say confirmation IDs, booking IDs, or reference numbers out loud.
- Never say "I'll log this", "let me check", "just a moment", or backend commentary.
- Never describe what tool you are calling. Call it silently, then give the result naturally.
- After booking: confirm conversationally. Example: "Wonderful, you're booked for Saturday at 10 AM!"
- Never make up property data. Only use what search_properties returns.
- No bullet points, no markdown, no emojis — spoken words only.
- If lead speaks Hindi, reply in a warm Hindi-English mix.
- Never ask more than one question at a time.
- If they are busy, ask for a good callback time, then call update_call_outcome silently.
- Call update_call_outcome ONLY at the very end of the conversation."""


def build_outbound_prompt(call_type: str, lead: dict) -> str:
    name = lead.get("name", "there")
    interest = lead.get("interest", "a property")
    visit_date = lead.get("visit_date", "")
    visit_time = lead.get("visit_time", "")
    property_name = lead.get("property_name", "the property")

    if call_type == "follow_up":
        return f"""You are Priya, a warm voice agent for Prestige Realty in Bangalore.
You are calling {name} who recently enquired about {interest}.
1. Introduce yourself warmly and confirm you are speaking with {name}.
2. Ask if they are free to talk for a couple of minutes.
3. Understand their requirement — location, BHK, budget.
4. Call search_properties silently, then share the best match conversationally.
5. Offer to book a site visit with book_site_visit.
6. At the very end, call update_call_outcome silently.
{_BASE_RULES}"""

    if call_type == "visit_reminder":
        return f"""You are Priya, a warm voice agent for Prestige Realty in Bangalore.
You are calling {name} to remind them about their site visit on {visit_date} at {visit_time} for {property_name}.
1. Introduce yourself warmly and confirm you are speaking with {name}.
2. Confirm their visit naturally — mention the date, time, and property.
3. Ask if they have any questions before the visit.
4. If they need to reschedule, use book_site_visit to find a new slot.
5. At the very end, call update_call_outcome silently.
{_BASE_RULES}"""

    if call_type == "new_launch":
        return f"""You are Priya, a warm voice agent for Prestige Realty in Bangalore.
You are calling {name} about a new launch matching their interest in {interest}.
1. Introduce yourself warmly and confirm you are speaking with {name}.
2. In one or two natural sentences, mention the new launch and why it matches their interest.
3. Call search_properties silently to get details, then share one key highlight.
4. Offer an early-bird site visit with book_site_visit.
5. At the very end, call update_call_outcome silently.
{_BASE_RULES}"""

    return f"""You are Priya, a warm voice agent for Prestige Realty in Bangalore.
You are calling {name} regarding their property interest.
Introduce yourself warmly, understand their need, and help them take the next step.
{_BASE_RULES}"""


# ---------------------------------------------------------------------------
# Dial helper
# ---------------------------------------------------------------------------


async def dial_lead(
    to_number: str,
    from_number: str,
    vobiz_auth_id: str,
    vobiz_auth_token: str,
    answer_url: str,
) -> dict:
    """Trigger an outbound call via the Vobiz REST API.

    Args:
        to_number: Lead's phone number with country code, e.g. +919876543210.
        from_number: Your Vobiz DID number.
        vobiz_auth_id: Vobiz X-Auth-ID from console.vobiz.ai.
        vobiz_auth_token: Vobiz X-Auth-Token from console.vobiz.ai.
        answer_url: Public HTTP URL Vobiz fetches to get VoiceXML when call connects.

    Returns:
        Vobiz API response dict.
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://api.vobiz.ai/api/v1/Account/{vobiz_auth_id}/Call/",
            headers={
                "X-Auth-ID": vobiz_auth_id,
                "X-Auth-Token": vobiz_auth_token,
                "Content-Type": "application/json",
            },
            json={
                "from": from_number,
                "to": to_number,
                "answer_url": answer_url,
                "answer_method": "POST",
            },
        ) as resp:
            result = await resp.json()
            logger.info(f"Vobiz dial response for {to_number}: {result}")
            return result


# ---------------------------------------------------------------------------
# Pipeline builder
# ---------------------------------------------------------------------------


async def run_outbound(
    transport: FastAPIWebsocketTransport,
    session_token: str,
    deepgram_api_key: str,
    groq_api_key: str,
    sarvam_api_key: str,
) -> None:
    """Build and run the outbound call pipeline for a given session.

    Args:
        transport: The FastAPIWebsocketTransport connected to Vobiz.
        session_token: Token identifying the pre-stored lead context.
        deepgram_api_key: Deepgram API key.
        groq_api_key: Groq API key for ultra-low latency LLM inference.
        sarvam_api_key: Sarvam API key.
    """
    lead_context = pending_outbound_sessions.pop(session_token, {})
    if not lead_context:
        logger.warning(f"No session found for token {session_token}. Using empty context.")

    call_type = lead_context.get("call_type", "follow_up")
    system_prompt = build_outbound_prompt(call_type, lead_context)

    # --- STT ---
    stt = DeepgramSTTService(
        api_key=deepgram_api_key,
        settings=DeepgramSTTService.Settings(
            model="nova-3-phonecall",
            endpointing=150,
            utterance_end_ms=800,
            interim_results=True,
            smart_format=True,
            punctuate=True,
        ),
    )

    # --- LLM ---
    # Groq: ~100-150ms inference vs ~400-600ms OpenAI — saves 300-500ms every turn.
    llm = GroqLLMService(
        api_key=groq_api_key,
        model="llama-3.3-70b-versatile",
    )

    # --- TTS ---
    tts = SarvamTTSService(
        api_key=sarvam_api_key,
        settings=SarvamTTSService.Settings(
            voice="priya",
            model="bulbul:v3",
            pace=1.05,
            temperature=0.65,
            min_buffer_size=25,
            max_chunk_length=250,
        ),
    )

    # --- Context + aggregator ---
    context = LLMContext(tools=OUTBOUND_TOOLS)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            # VAD ONLY here in the aggregator — not on the transport.
            # Dual VAD causes the aggregator to go deaf after the opener.
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(min_volume=0.6, confidence=0.6, stop_secs=0.6)
            ),
            user_turn_strategies=UserTurnStrategies(
                stop=[SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=0.7)],
            ),
            user_turn_stop_timeout=2.0,
        ),
    )

    # --- Pipeline ---
    pipeline = Pipeline([
        transport.input(),
        stt,
        user_aggregator,
        llm,
        tts,
        transport.output(),
        assistant_aggregator,
    ])

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True),
        enable_rtvi=False,
    )

    # --- Events ---

    @transport.event_handler("on_client_connected")
    async def on_client_connected(_transport, _client):
        logger.info(f"Outbound call connected | call_type={call_type} | lead={lead_context.get('name')}")
        context.add_message({
            "role": "user",
            "content": "[call connected — the lead just picked up. Introduce yourself warmly with a natural opening sentence.]",
        })
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, _client):
        logger.info("Outbound call disconnected")
        await worker.cancel()

    # --- Run ---
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    await runner.run()

"""
Outbound Call Agent — Prestige Realty

Triggered by a POST to /dial with the lead's details.
Server stores the lead context in memory keyed by a session token,
calls the Vobiz REST API to dial the lead,
Vobiz opens a WebSocket to /ws/outbound?session=<token>,
and the pipeline picks up the pre-stored lead context.

Three outbound call types (set via call_type in the /dial payload):
  follow_up     — Lead submitted a form, following up on their enquiry
  visit_reminder — Remind about an upcoming site visit
  new_launch    — Inform a past lead about a new property matching their criteria
"""

import asyncio
import aiohttp
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import TTSSpeakFrame, Frame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
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
from pipecat.turns.user_mute import AlwaysUserMuteStrategy, FunctionCallUserMuteStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from prewarmed_services import PrewarmedDeepgramSTTService as DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport
from pipecat.workers.runner import WorkerRunner

from tools import OUTBOUND_TOOLS

# ---------------------------------------------------------------------------
# Session store — maps session_token → lead context dict
# In production, use Redis or a DB so multiple server instances share state.
# ---------------------------------------------------------------------------

pending_outbound_sessions: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# System prompts — one per call type
# ---------------------------------------------------------------------------

_BASE_RULES = """
CONVERSATION RULES:
- Your opening greeting must be ONE short sentence only.
- If the lead says "hello" or "hi" at the start of the call, they may not have heard your initial greeting. Briefly introduce yourself and state why you are calling.
- Lead speech sometimes arrives as multiple short messages in a row. Treat them as one continuous sentence.

PHONE CALL SPEAKING RULES:
- Speak in 1 to 2 complete, naturally flowing sentences per response.
- Start your responses with a short conversational filler (e.g., "Got it, ", "Sure, ", "Okay, ") so you can begin speaking immediately while thinking.
- Use natural contractions (e.g., "I've", "You'll", "Let's") and smooth connectors ("So what I can do is,", "That's great, just to confirm,").
- Never say confirmation IDs, booking IDs, reference numbers, or RERA numbers. Never.
- Before calling search_properties, calculate_emi, or book_site_visit, say one short warm sentence first so there is no silence. Example: "Sure, let me check what's available for you." or "Let me work out those numbers." Then immediately make the tool call.
- Never say "I'll log this", "let me check", "just a moment", or any backend commentary.
- Never describe what tool you are calling. Call it silently and give the result naturally.
- After booking: confirm with date and time only. Example: "Wonderful, you are booked for Saturday the 25th at 10 in the morning."
- When describing property features, weave them into natural sentences. Never list them with commas one after another.
- Never make up property data. Only use what search_properties returns.
- No bullet points, no numbered lists, no markdown, no asterisks, no emojis. Spoken words only.
- If lead speaks Hindi, reply in a warm Hindi-English mix.
- Never ask more than one question at a time.
- If they are busy, ask for a good callback time, then call update_call_outcome silently.
- Call update_call_outcome ONLY at the very end of the conversation, not before.
- After you have said your farewell and update_call_outcome is done, call end_call silently to hang up. Never mention that you are ending the call.

TTS PRONUNCIATION RULES — follow these exactly for natural phone audio:
- Apartment sizes: say conversational real estate terms like "3 BHK apartment" or "2 BHK". Never "2BHK", "3 BHK", or "BHK" alone.
- Money in lakhs: say "85 lakhs" or "90 lakhs". Never "85L", "85 L", or any short form.
- Money in crores: say "1.5 crores" or "2 crores". Never "1.5 Cr", "2 Cr", or any short form.
- Area: always say "square feet". Never "sq ft", "sqft", or "sq.ft".
- Monthly repayment: say "around 65 thousand rupees a month". Never use "EMI" as a word.
- Large numbers: say "65 thousand" not "65,000". Say "1 lakh 20 thousand" not "1,20,000".
- Percentages: say "8.5 percent" not "8.5%".
- Dates: say "the 25th of June" or "Saturday the 25th". Never read out a date like "2026-06-25".
- Never use ellipsis. End every sentence cleanly.
- No brackets or parentheses anywhere in your response.
- TOOL CALLING SPEED: When calling tools like book_site_visit or calculate_emi, NEVER say "Just a moment", "Hold on", or "Let me check". Instead, call the tool AND immediately speak the confirmation in the exact same turn! For example, when calling book_site_visit, call the tool and say "Thank you Aditya, your site visit is confirmed for tomorrow morning at 10 o'clock! We look forward to seeing you." immediately."""


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
# Dial helper — calls Vobiz REST API to initiate an outbound call
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

class OpenerProtectionFilter(FrameProcessor):
    """Prevents initial phone connection noise/echo from interrupting the bot opener."""
    def __init__(self, protection_duration_secs: float = 2.5):
        super().__init__()
        self._protection_duration = protection_duration_secs
        self._protection_end_time = 0.0

    def start_protection(self, duration_override: float = None):
        import time
        dur = duration_override if duration_override is not None else self._protection_duration
        self._protection_end_time = time.time() + dur

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        import time
        if direction == FrameDirection.DOWNSTREAM and time.time() < self._protection_end_time:
            from pipecat.frames.frames import UserStartedSpeakingFrame, TranscriptionFrame, InterruptionFrame
            if isinstance(frame, (UserStartedSpeakingFrame, TranscriptionFrame, InterruptionFrame)):
                return
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)


async def run_outbound(
    transport: FastAPIWebsocketTransport,
    session_token: str,
    deepgram_api_key: str,
    openai_api_key: str,
    sarvam_api_key: str,
    system_prompt: str,
    voice: str,
    company_name: str,
    knowledge_base: str,
    niche: str,
    agent_config: dict = None,
    lead_context: dict = None,
) -> list:
    """Build and run the outbound call pipeline for a given session."""
    if lead_context is None:
        lead_context = pending_outbound_sessions.pop(session_token, {})
    if not lead_context:
        logger.warning(f"No session found for token {session_token}. Using empty context.")

    agent_config = agent_config or lead_context.get("agent_config", {})
    call_type = lead_context.get("call_type", "follow_up")
    
    outbound_directive = (
        f"CRITICAL: THIS IS AN OUTBOUND CALL.\n"
        f"You are calling {lead_context.get('name', 'a customer')} regarding their interest in {lead_context.get('interest', 'property')}.\n"
        f"THE SYSTEM HAS ALREADY SPOKEN YOUR OPENING GREETING TO THE USER ON YOUR BEHALF.\n"
        f"DO NOT introduce yourself. DO NOT say 'Hi' or 'Hello' or repeat the company name.\n"
        f"Assume the user just heard you ask 'Is this a good time to talk?'.\n"
        f"Your FIRST response MUST simply react to whatever the user just said (e.g., 'Great, let me tell you about...')."
    )

    # We combine the UI-configured persona with the dynamic lead context
    system_prompt_final = (
        f"You are representing: {company_name}\n\n"
        f"{system_prompt}\n\n"
        f"{outbound_directive}\n\n"
        f"--- KNOWLEDGE BASE ---\n{knowledge_base}\n\n"
        f"--- CALL CONTEXT ---\n"
        f"Lead Name: {lead_context.get('name', 'Unknown')}\n"
        f"Call Type: {call_type}\n"
        f"Interest: {lead_context.get('interest', 'Unknown')}\n"
        f"{_BASE_RULES}"
    )

    # --- Dynamic Services via Service Factory ---
    from service_factory import create_stt_service, create_llm_service, create_tts_service
    stt_provider = agent_config.get("stt_provider", "deepgram")
    stt_model = agent_config.get("stt_model", "nova-2-conversationalai")
    stt_keywords = agent_config.get("stt_keywords", "")
    stt_timeout = agent_config.get("stt_timeout", "500ms")
    stt_eager = agent_config.get("stt_eager", "enabled")
    stt_language = agent_config.get("stt_language", "en")
    stt = lead_context.pop("prewarmed_stt", None) or create_stt_service(provider=stt_provider, model=stt_model, language=stt_language, prewarmed=False, keywords=stt_keywords, timeout=stt_timeout, eager=stt_eager)

    llm_provider = agent_config.get("llm_provider", "openai")
    llm_model = agent_config.get("llm_model", "gpt-4o-mini")
    llm_temp = agent_config.get("llm_temperature", 0.7)
    llm = create_llm_service(llm_provider, llm_model, llm_temp)
    llm._settings.system_instruction = system_prompt_final

    tts_provider = agent_config.get("tts_provider", "sarvam")
    tts_engine_model = agent_config.get("tts_engine_model", "bulbul-v3")
    tts_voice = agent_config.get("tts_voice", voice)
    tts_speed = agent_config.get("tts_speed", 1.1)
    tts = lead_context.pop("prewarmed_tts", None) or create_tts_service(tts_provider, tts_voice, tts_speed, prewarmed=False, engine_model=tts_engine_model)

    # --- Context + aggregator ---
    from tools import OUTBOUND_TOOLS, update_call_outcome
    tools_to_use = OUTBOUND_TOOLS if niche == "real_estate" else [update_call_outcome]
    context = LLMContext(tools=tools_to_use)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            user_mute_strategies=[
                AlwaysUserMuteStrategy(),
                FunctionCallUserMuteStrategy(),
            ],
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(min_volume=0.1, confidence=0.5, stop_secs=0.2)
            ),
            user_turn_strategies=UserTurnStrategies(
                stop=[SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=0.2, wait_for_transcript=False)],
            ),
            user_turn_stop_timeout=1.0,
        ),
    )

    opener_protection = OpenerProtectionFilter(protection_duration_secs=2.5)

    # --- Pipeline ---
    pipeline = Pipeline([
        transport.input(),
        stt,
        opener_protection,
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
    async def on_client_connected(_transport, client_ws):
        logger.info(f"Outbound call connected | call_type={call_type} | lead={lead_context.get('name')}")
        lead_name = lead_context.get("name", "")
        company = company_name if company_name else "our company"
        from prompt_engine import render_template
        raw_opener = agent_config.get("opener_text") or lead_context.pop("opener_text", None) or (
            f"Hi, is this {{lead_name}}? I'm calling from {{company_name}}."
            if lead_name
            else f"Hi, I'm calling from {{company_name}}. Am I speaking with the right person?"
        )
        render_ctx = {
            "lead_name": lead_name,
            "company_name": company,
            "name": agent_config.get("name", "AI Assistant"),
            "niche": niche
        }
        opener = render_template(raw_opener, render_ctx)
        context.add_message({"role": "assistant", "content": opener})
        lead_context.pop("opener_pcm", None)
        lead_context.pop("opener_text", None)

        logger.info(f"Speaking opener via live WebSocket TTS (100% voice parity): {opener}")
        opener_protection.start_protection(duration_override=2.5)
        await worker.queue_frames([TTSSpeakFrame(text=opener, append_to_context=False)])










    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, _client):
        logger.info("Outbound call disconnected")
        await worker.cancel()

    # --- Run ---
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    await runner.run()
    
    return context.get_messages()

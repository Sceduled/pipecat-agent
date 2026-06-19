"""
Inbound Call Agent — Prestige Realty

Triggered when a customer dials your Vobiz DID number.
Vobiz fetches /voice-xml/inbound, gets the Stream directive,
then opens a WebSocket to /ws/inbound.

Agent persona: Priya — warm, professional, concise (it's a phone call).
"""

import asyncio
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
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport
from pipecat.workers.runner import WorkerRunner

from tools import INBOUND_TOOLS

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

INBOUND_SYSTEM_PROMPT = """You are Priya, a warm and professional voice agent for Prestige Realty in Bangalore.

A customer just called. Follow this flow:
1. Greet and ask how you can help.
2. Find out: location, BHK, budget, purpose (buy/rent/invest).
3. Call search_properties silently, then present the best option.
4. Answer questions using get_property_details or calculate_emi.
5. Offer to book a site visit with book_site_visit.
6. Once you have their name and phone, call save_lead.
7. If they want a human, call transfer_to_agent.

PHONE CALL SPEAKING RULES — follow these exactly:
- Speak in 1 to 2 complete, naturally flowing sentences per response.
- Use smooth connectors: "So, I can help you with that —", "That sounds perfect!", "Great, and just to check..."
- Never say confirmation IDs, booking IDs, or reference numbers out loud.
- Never say "I'll log this", "let me check", "just a moment", or any backend commentary.
- Never describe what tool you are calling. Just call it silently and give the result naturally.
- After booking: confirm conversationally. Example: "Perfect, you're booked for Saturday at 10 AM!"
- Never make up property data. Only use what search_properties returns.
- No bullet points, no markdown, no emojis — spoken words only.
- If caller speaks Hindi, reply in a warm Hindi-English mix.
- Never ask more than one question at a time."""


# ---------------------------------------------------------------------------
# Pipeline builder
# ---------------------------------------------------------------------------


async def run_inbound(
    transport: FastAPIWebsocketTransport,
    deepgram_api_key: str,
    openai_api_key: str,
    sarvam_api_key: str,
) -> None:
    """Build and run the inbound call pipeline.

    Args:
        transport: The FastAPIWebsocketTransport connected to Vobiz.
        deepgram_api_key: Deepgram API key for STT.
        openai_api_key: OpenAI API key for LLM.
        sarvam_api_key: Sarvam API key for TTS.
    """
    # --- STT ---
    # nova-2-phonecall: tuned for G.711 µ-law telephone audio.
    # endpointing=300ms: Deepgram fires final transcript 300ms after speech stops
    # (default never fires on phone lines because background noise prevents silence).
    stt = DeepgramSTTService(
        api_key=deepgram_api_key,
        settings=DeepgramSTTService.Settings(
            model="nova-2-phonecall",
            endpointing=300,
            utterance_end_ms=1000,
            interim_results=True,
        ),
    )

    # --- LLM ---
    llm = OpenAILLMService(
        api_key=openai_api_key,
        settings=OpenAILLMService.Settings(
            model="gpt-4o-mini",
            system_instruction=INBOUND_SYSTEM_PROMPT,
        ),
    )

    # --- TTS ---
    # WebSocket streaming: first audio arrives in ~0.4s (vs 3+ s for HTTP).
    # min_buffer_size=80: Sarvam accumulates 80 chars before starting synthesis,
    # so each short sentence is ONE synthesis job → smooth continuous audio.
    # (With min_buffer_size=25, every 25-char burst is separate → word-by-word.)
    tts = SarvamTTSService(
        api_key=sarvam_api_key,
        settings=SarvamTTSService.Settings(
            voice="priya",
            model="bulbul:v3",
            pace=1.05,
            temperature=0.65,
            min_buffer_size=80,
            max_chunk_length=200,
        ),
    )

    # --- Context + aggregator ---
    context = LLMContext(tools=INBOUND_TOOLS)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            # min_volume=0.1: phone audio amplitude is ~0.05–0.25 (µ-law decoded).
            # The default 0.6 never triggers on phone lines — bot goes deaf after opener.
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(min_volume=0.1, confidence=0.5, stop_secs=0.5)
            ),
            user_turn_strategies=UserTurnStrategies(
                stop=[SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=0.6)],
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
        logger.info("Inbound call connected — waiting for phone line to settle")
        # Phone lines emit a brief noise burst (click/ringback artifact) within the
        # first 600ms of WebSocket open. Without this delay the burst triggers VAD,
        # which interrupts the in-flight LLM opener request and silences the bot for
        # the rest of the call.
        await asyncio.sleep(1.0)
        logger.info("Queuing greeting")
        context.add_message({
            "role": "user",
            "content": "[call connected — greet the customer warmly with a natural opening sentence and ask how you can help]",
        })
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, _client):
        logger.info("Inbound call disconnected")
        await worker.cancel()

    # --- Run ---
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    await runner.run()

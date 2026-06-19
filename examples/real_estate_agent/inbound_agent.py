"""
Inbound Call Agent — Prestige Realty

Triggered when a customer dials your Vobiz DID number.
Vobiz fetches /voice-xml/inbound, gets the Stream directive,
then opens a WebSocket to /ws/inbound.
"""

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
- Speak in 1 to 3 complete, naturally connected sentences per response.
- Use smooth connectors: "So, I can help you with that — let me just ask...", "Great, and just to check...", "That sounds perfect!"
- Never say confirmation IDs, booking IDs, or reference numbers out loud.
- Never say "I'll log this", "let me check", "just a moment", or any backend commentary.
- Never describe what tool you are calling. Just call it silently and give the result naturally.
- After booking: say the date and time conversationally. Example: "Perfect, I've got you booked for Saturday at 10 AM!"
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
    groq_api_key: str,
    sarvam_api_key: str,
) -> None:
    """Build and run the inbound call pipeline.

    Args:
        transport: The FastAPIWebsocketTransport connected to Vobiz.
        deepgram_api_key: Deepgram API key for STT.
        groq_api_key: Groq API key for LLM (ultra-low latency inference).
        sarvam_api_key: Sarvam API key for TTS.
    """
    # --- STT ---
    # nova-3-phonecall: best accuracy + lowest latency for phone audio.
    # endpointing=150ms: detects end-of-speech fast on telephony.
    # interim_results=True: lets Deepgram send partial transcripts so the
    # aggregator can start turn detection earlier.
    stt = DeepgramSTTService(
        api_key=deepgram_api_key,
        settings=DeepgramSTTService.Settings(
            model="nova-2-phonecall",
            endpointing=150,
            utterance_end_ms=800,
            interim_results=True,
            smart_format=True,
            punctuate=True,
        ),
    )

    # --- LLM ---
    # Groq runs llama-3.3-70b at ~100-150ms vs OpenAI gpt-4o-mini at ~400-600ms.
    # This alone saves 300-500ms every single turn — the single biggest code-level
    # latency win available.
    llm = GroqLLMService(
        api_key=groq_api_key,
        settings=GroqLLMService.Settings(
            model="llama-3.3-70b-versatile",
            system_instruction=INBOUND_SYSTEM_PROMPT,
        ),
    )

    # --- TTS ---
    # SarvamTTSService streams over WebSocket — first audio at ~30 chars buffered.
    # bulbul:v3 is the most natural Indian-English voice at 24kHz.
    # min_buffer_size=25: start streaming even sooner for shorter responses.
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
    context = LLMContext(tools=INBOUND_TOOLS)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            # VAD lives HERE in the aggregator — NOT on the transport.
            # Having VAD in both places causes a conflict where the aggregator
            # sees pre-filtered audio, never detects a new turn, and the AI
            # goes silent after the opening greeting.
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
        logger.info("Inbound call connected — queuing greeting")
        context.add_message({
            "role": "user",
            "content": "[call connected — greet the customer warmly with a natural opening sentence and ask how you can help them today]",
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

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
from pipecat.frames.frames import TTSSpeakFrame
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
1. Greet with ONE short sentence and ask how you can help.
2. Find out: location, apartment size, budget, and purpose (buy, rent, or invest).
3. Call search_properties silently, then describe the best match in one or two natural sentences.
4. Answer questions using get_property_details or calculate_emi.
5. Offer to book a site visit with book_site_visit.
6. Once you have their name and phone, call save_lead silently.
7. If they want a human agent, call transfer_to_agent.

CONVERSATION RULES:
- Your opening greeting must be ONE short sentence only. Example: "Hi, this is Priya from Prestige Realty. How can I help you today?"
- Once you have introduced yourself, NEVER say your name or company again. Just continue naturally.
- If the user says "hello" or "hi" after your greeting, treat it as a natural continuation, not a cue to re-introduce.
- User speech sometimes arrives as multiple short messages in a row. Treat them as one continuous sentence.

PHONE CALL SPEAKING RULES:
- Speak in 1 to 2 complete, naturally flowing sentences per response.
- Start your responses with a short conversational filler (e.g., "Got it, ", "Sure, ", "Okay, ") so you can begin speaking immediately while thinking.
- Use natural contractions (e.g., "I've", "You'll", "Let's") and smooth connectors ("So I can help you with that,", "That sounds perfect!").
- Never say confirmation IDs, booking IDs, reference numbers, or RERA numbers. Never.
- Never say "I'll log this", "let me check", "just a moment", or any backend commentary.
- Never describe what tool you are calling. Call it silently and give the result naturally.
- After booking: confirm with date and time only. Example: "Perfect, you are booked for Saturday the 25th at 10 in the morning."
- When describing property features, weave them into natural sentences. Never list them with commas one after another.
- Never make up property data. Only use what search_properties returns.
- No bullet points, no numbered lists, no markdown, no asterisks, no emojis. Spoken words only.
- If caller speaks Hindi, reply in a warm Hindi-English mix.
- Never ask more than one question at a time.

TTS PRONUNCIATION RULES — follow these exactly for natural phone audio:
- Apartment sizes: always say "two B H K" or "three B H K". Never "2BHK", "3 BHK", or "BHK" alone.
- Money in lakhs: say "85 lakhs" or "90 lakhs". Never "85L", "85 L", or any short form.
- Money in crores: say "1.5 crores" or "2 crores". Never "1.5 Cr", "2 Cr", or any short form.
- Area: always say "square feet". Never "sq ft", "sqft", or "sq.ft".
- Monthly repayment: say "around 65 thousand rupees a month". Never use "EMI" as a word.
- Large numbers: say "65 thousand" not "65,000". Say "1 lakh 20 thousand" not "1,20,000".
- Percentages: say "8.5 percent" not "8.5%".
- Dates: say "the 25th of June" or "Saturday the 25th". Never read out a date like "2026-06-25".
- Never use em-dashes, en-dashes, or hyphens between clauses. Use a comma or period instead.
- Never use ellipsis. End every sentence cleanly.
- No brackets or parentheses anywhere in your response."""


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
            min_buffer_size=50,
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
                stop=[SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=0.4)],
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
        opener = "Hi, this is Priya from Prestige Realty. How can I help you today?"
        # Add greeting to context NOW (synchronous, before any await) so any user
        # speech during the startup window sees a prior assistant turn and the LLM
        # won't re-introduce. TTSSpeakFrame(append_to_context=False) synthesizes the
        # audio without double-adding the message after TTS finishes.
        context.add_message({"role": "assistant", "content": opener})
        # 0.8s guard: phone lines emit a noise burst at ~600ms that fires VAD and
        # would interrupt TTS. We start synthesis only after it has passed.
        await asyncio.sleep(0.8)
        logger.info("Queuing greeting via TTSSpeakFrame")
        await worker.queue_frames([TTSSpeakFrame(text=opener, append_to_context=False)])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, _client):
        logger.info("Inbound call disconnected")
        await worker.cancel()

    # --- Run ---
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    await runner.run()

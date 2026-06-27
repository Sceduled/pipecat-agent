"""
ring_phase_synth.py — Bolna-style ring-phase opener pre-synthesis.

During the Vobiz ring phase (while lead's phone rings, ~5-10s), this module:
  1. Calls Sarvam's simple REST API to synthesize the opener text into raw PCM bytes.
  2. Stores the bytes in the session dict so the WebSocket handler can stream them
     instantly the moment the lead answers — zero TTS cold-start penalty.

This is a pure HTTP call with NO pipecat pipeline dependencies, so it works
cleanly outside the pipeline lifecycle. No TaskManager, no WebSocket service
objects required.
"""

import asyncio
import base64
import struct

import aiohttp
from loguru import logger


# ---------------------------------------------------------------------------
# Sarvam WebSocket API call — matches live TTS vocoder exactly
# ---------------------------------------------------------------------------

async def synthesize_opener(
    *,
    api_key: str,
    text: str,
    voice: str,
    sample_rate: int = 24000,
) -> bytes | None:
    """Call Sarvam WebSocket TTS and return raw signed-16-bit PCM bytes.

    Returns None on any error so the caller can fall back to live TTS.
    """
    v_clean = (voice or "shubh").replace("sarvam:", "").lower()
    if v_clean not in ["shubh", "bulbul", "arjun", "priya", "anushka", "kabir", "roopa", "aayan", "ashutosh", "advait", "amelia", "sophia"]:
        logger.info(f"ring_phase_synth: Voice '{voice}' is non-Sarvam — skipping pre-synth")
        return None

    url = "wss://api.sarvam.ai/text-to-speech/ws"
    headers = {
        "api-subscription-key": api_key,
    }
    config_data = {
        "target_language_code": "en-IN",
        "speaker": v_clean,
        "speech_sample_rate": str(sample_rate),
        "enable_preprocessing": True,
        "min_buffer_size": 50,
        "max_chunk_length": 150,
        "output_audio_codec": "linear16",
        "output_audio_bitrate": "128000",
        "pace": 1.0,
        "model": "bulbul:v3",
    }

    try:
        from websockets.asyncio.client import connect as websocket_connect
        import json as _json
        audio_chunks = []
        async with websocket_connect(url, additional_headers=headers, open_timeout=6) as ws:
            await ws.send(_json.dumps({"type": "config", "data": config_data}))
            await ws.send(_json.dumps({"type": "text", "data": {"text": text}}))

            while True:
                try:
                    msg_raw = await asyncio.wait_for(ws.recv(), timeout=6.0)
                except asyncio.TimeoutError:
                    break
                if isinstance(msg_raw, str):
                    msg = _json.loads(msg_raw)
                    msg_type = msg.get("type")
                    if msg_type == "audio":
                        audio_b64 = msg.get("data", {}).get("audio")
                        if audio_b64:
                            audio_chunks.append(base64.b64decode(audio_b64))
                    elif msg_type == "event" and msg.get("data", {}).get("event_type") == "final":
                        break
                    elif msg_type == "error":
                        logger.warning(f"ring_phase_synth: Sarvam WS returned error: {msg}")
                        return None
        if not audio_chunks:
            logger.warning("ring_phase_synth: No audio chunks received from Sarvam WS")
            return None
        raw = b"".join(audio_chunks)
        logger.info(f"ring_phase_synth: Synthesized {len(raw)} PCM bytes via Sarvam WebSocket for opener")
        return raw
    except Exception as e:
        logger.warning(f"ring_phase_synth: WS call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Split large PCM blob into 20ms chunks for smooth streaming
# ---------------------------------------------------------------------------

CHUNK_DURATION_MS = 20

def pcm_to_chunks(pcm_bytes: bytes, sample_rate: int = 24000) -> list[bytes]:
    """Split raw PCM bytes into 20ms frames for smooth transport streaming."""
    bytes_per_ms = (sample_rate * 2) // 1000  # 16-bit mono = 2 bytes/sample
    chunk_size = bytes_per_ms * CHUNK_DURATION_MS
    return [pcm_bytes[i:i + chunk_size] for i in range(0, len(pcm_bytes), chunk_size)]

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
# Sarvam REST API call — totally independent of pipecat services
# ---------------------------------------------------------------------------

async def synthesize_opener(
    *,
    api_key: str,
    text: str,
    voice: str,
    sample_rate: int = 24000,
) -> bytes | None:
    """Call Sarvam REST TTS and return raw signed-16-bit PCM bytes.

    Returns None on any error so the caller can fall back to live TTS.
    """
    url = "https://api.sarvam.ai/text-to-speech"
    payload = {
        "text": text,
        "target_language_code": "en-IN",
        "speaker": voice,
        "sample_rate": sample_rate,
        "enable_preprocessing": True,
        "model": "bulbul:v3",
        "pace": 1.05,
        "temperature": 0.65,
    }
    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    logger.warning(f"ring_phase_synth: Sarvam REST returned {resp.status}")
                    return None
                data = await resp.json()
    except Exception as e:
        logger.warning(f"ring_phase_synth: REST call failed: {e}")
        return None

    try:
        audios = data.get("audios", [])
        if not audios:
            logger.warning("ring_phase_synth: No audios in response")
            return None
        raw = base64.b64decode(audios[0])
        # Strip WAV header if present (starts with 'RIFF')
        if raw[:4] == b"RIFF":
            raw = raw[44:]
        logger.info(f"ring_phase_synth: Synthesized {len(raw)} PCM bytes for opener")
        return raw
    except Exception as e:
        logger.warning(f"ring_phase_synth: Decode failed: {e}")
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

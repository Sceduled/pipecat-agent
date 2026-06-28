"""
test_connections.py — End-to-end connection verification for all AI services.

Tests:
  1. Sarvam REST API (ring-phase synthesis) — does it return audio bytes?
  2. Sarvam TTS WebSocket — does it connect and accept config?
  3. Deepgram STT WebSocket — does it connect?
  4. OpenAI LLM — does a minimal chat completion work?

Run with:
  python test_connections.py
"""

import asyncio
import base64
import json
import os
import sys

import aiohttp
from loguru import logger

# Load env from .env file if present
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

load_env()

SARVAM_API_KEY  = os.environ.get("SARVAM_API_KEY", "")
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
OPENAI_API_KEY  = os.environ.get("OPENAI_API_KEY", "")

PASS = "[PASS]"
FAIL = "[FAIL]"

# ---------------------------------------------------------------------------
# Test 1: Sarvam REST (ring-phase synth)
# ---------------------------------------------------------------------------

async def test_sarvam_rest():
    name = "Sarvam REST TTS"
    if not SARVAM_API_KEY:
        print(f"{FAIL}  {name}: SARVAM_API_KEY not set")
        return False
    try:
        payload = {
            "text": "Hi, is this a good time to talk?",
            "target_language_code": "en-IN",
            "speaker": "shubh",
            "sample_rate": 24000,
            "enable_preprocessing": True,
            "model": "bulbul:v3",
            "pace": 1.05,
            "temperature": 0.65,
        }
        headers = {"api-subscription-key": SARVAM_API_KEY, "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.sarvam.ai/text-to-speech",
                json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    print(f"{FAIL}  {name}: HTTP {resp.status} — {text[:120]}")
                    return False
                data = await resp.json()
        audios = data.get("audios", [])
        if not audios:
            print(f"{FAIL}  {name}: No audio in response")
            return False
        pcm = base64.b64decode(audios[0])
        if pcm[:4] == b"RIFF":
            pcm = pcm[44:]
        print(f"{PASS}  {name}: {len(pcm)} raw PCM bytes returned (voice=shubh)")
        return True
    except Exception as e:
        print(f"{FAIL}  {name}: {e}")
        return False


# ---------------------------------------------------------------------------
# Test 2: Sarvam TTS WebSocket
# ---------------------------------------------------------------------------

async def test_sarvam_ws():
    name = "Sarvam TTS WebSocket"
    if not SARVAM_API_KEY:
        print(f"{FAIL}  {name}: SARVAM_API_KEY not set")
        return False
    try:
        from websockets.asyncio.client import connect as ws_connect
        uri = "wss://api.sarvam.ai/text-to-speech/ws"
        headers_ws = {"api-subscription-key": SARVAM_API_KEY}
        async with ws_connect(uri, additional_headers=headers_ws, open_timeout=8) as ws:
            config = {
                "target_language_code": "en-IN",
                "speaker": "shubh",
                "speech_sample_rate": "24000",
                "enable_preprocessing": True,
                "min_buffer_size": 20,
                "max_chunk_length": 200,
                "output_audio_codec": "linear16",
                "output_audio_bitrate": "128k",
                "pace": 1.05,
                "model": "bulbul:v3",
                "temperature": 0.65,
            }
            await ws.send(json.dumps(config))
            # Send a small text chunk
            await ws.send(json.dumps({"text": "Hello."}))
            # Expect at least one audio chunk back within 5s
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                size = len(msg) if isinstance(msg, bytes) else len(msg.encode())
                print(f"{PASS}  {name}: Connected + received {size} bytes audio chunk")
            except asyncio.TimeoutError:
                print(f"{FAIL}  {name}: Connected but no audio chunk received within 5s")
                return False
        return True
    except Exception as e:
        print(f"{FAIL}  {name}: {e}")
        return False


# ---------------------------------------------------------------------------
# Test 3: Deepgram STT WebSocket
# ---------------------------------------------------------------------------

async def test_deepgram_ws():
    name = "Deepgram STT WebSocket"
    if not DEEPGRAM_API_KEY:
        print(f"{FAIL}  {name}: DEEPGRAM_API_KEY not set")
        return False
    try:
        from websockets.asyncio.client import connect as ws_connect
        uri = (
            "wss://api.deepgram.com/v1/listen"
            "?model=nova-2-phonecall&encoding=linear16&sample_rate=8000"
            "&channels=1&endpointing=300&interim_results=true"
        )
        headers_ws = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
        async with ws_connect(uri, additional_headers=headers_ws, open_timeout=8) as ws:
            # Deepgram sends a metadata message on connect
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                if data.get("type") == "Metadata":
                    print(f"{PASS}  {name}: Connected, received Metadata (request_id={data.get('request_id','')})")
                else:
                    print(f"{PASS}  {name}: Connected, first message type={data.get('type','?')}")
            except asyncio.TimeoutError:
                # Some plans don't send metadata immediately — connection still OK
                print(f"{PASS}  {name}: Connected (no immediate metadata, which is fine)")
        return True
    except Exception as e:
        print(f"{FAIL}  {name}: {e}")
        return False


# ---------------------------------------------------------------------------
# Test 4: OpenAI LLM
# ---------------------------------------------------------------------------

async def test_openai():
    name = "OpenAI LLM (gpt-4o-mini)"
    if not OPENAI_API_KEY:
        print(f"{FAIL}  {name}: OPENAI_API_KEY not set")
        return False
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Reply with exactly: ok"}],
            "max_tokens": 5,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    print(f"{FAIL}  {name}: HTTP {resp.status} — {text[:120]}")
                    return False
                data = await resp.json()
        reply = data["choices"][0]["message"]["content"].strip()
        print(f"{PASS}  {name}: Response='{reply}'")
        return True
    except Exception as e:
        print(f"{FAIL}  {name}: {e}")
        return False


# ---------------------------------------------------------------------------
# Test 5: Ring-phase synthesis round-trip (the new feature)
# ---------------------------------------------------------------------------

async def test_ring_phase_synth():
    name = "Ring-Phase Synthesis (new feature)"
    try:
        from ring_phase_synth import synthesize_opener, pcm_to_chunks
        pcm = await synthesize_opener(
            api_key=SARVAM_API_KEY,
            text="Hi, is this Adithya? I'm calling from Skyline Developers.",
            voice="shubh",
        )
        if not pcm:
            print(f"{FAIL}  {name}: synthesize_opener returned None")
            return False
        chunks = pcm_to_chunks(pcm, sample_rate=24000)
        duration_ms = len(chunks) * 20
        print(f"{PASS}  {name}: {len(pcm)} bytes -> {len(chunks)} chunks -> ~{duration_ms}ms audio")
        return True
    except Exception as e:
        print(f"{FAIL}  {name}: {e}")
        return False


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def main():
    print("\n" + "="*60)
    print("  AI Connection Verification Suite")
    print("="*60 + "\n")

    results = await asyncio.gather(
        test_sarvam_rest(),
        test_sarvam_ws(),
        test_deepgram_ws(),
        test_openai(),
        test_ring_phase_synth(),
        return_exceptions=True,
    )

    passed = sum(1 for r in results if r is True)
    total = len(results)

    print(f"\n{'='*60}")
    print(f"  Result: {passed}/{total} passed")
    if passed == total:
        print("  ALL SYSTEMS GO -- Ready for live calls")
    else:
        print("  WARNING: Fix the failing services before making calls")
    print("="*60 + "\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())

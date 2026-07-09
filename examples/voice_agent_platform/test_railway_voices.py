"""
Run this on Railway console (`python test_railway_voices.py`) to check all voices on this account and see which work.
"""
import os
import urllib.request
import json
import asyncio
import websockets

key = os.environ.get("ELEVENLABS_API_KEY", "")
if not key:
    print("ERROR: ELEVENLABS_API_KEY not set in environment!")
    exit(1)

print(f"Using API key: {key[:10]}...{key[-4:]}\n")

# 1. List all voices on this account
print("=== Listing all voices on this account ===")
try:
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/voices",
        headers={"xi-api-key": key}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        voices_data = json.loads(resp.read())

    for v in voices_data.get("voices", []):
        print(f"  [{v.get('category', '?'):10s}] {v.get('name', '?'):30s} id={v['voice_id']}")
except Exception as e:
    print(f"Failed to list voices: {e}")
    voices_data = {"voices": []}

# 2. Test WebSocket multi-stream-input for voices
async def test_ws(vid, name):
    url = f"wss://api.elevenlabs.io/v1/text-to-speech/{vid}/multi-stream-input?model_id=eleven_flash_v2_5&output_format=pcm_16000&auto_mode=true"
    try:
        async with websockets.connect(url, additional_headers={"xi-api-key": key}) as ws:
            await ws.send(json.dumps({"text": "Hello test.", "context_id": "diag"}))
            await ws.send(json.dumps({"text": "", "context_id": "diag"}))
            chunks = 0
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
                msg = json.loads(raw)
                if msg.get("audio"):
                    chunks += 1
                if msg.get("isFinal"):
                    break
            await ws.close()
            return f"{chunks} chunks (SUCCESS)" if chunks > 0 else "0 chunks (BLOCKED BY PLAN/LIBRARY RESTRICTION)"
    except Exception as e:
        return f"ERROR: {e}"

print("\n=== Testing WebSocket multi-stream-input (what Pipecat uses) ===")
async def run_ws_tests():
    for v in voices_data.get("voices", []):
        vid = v["voice_id"]
        name = v.get("name", "?")
        result = await test_ws(vid, name)
        print(f"  [WS] {name:30s} id={vid} -> {result}")

asyncio.run(run_ws_tests())

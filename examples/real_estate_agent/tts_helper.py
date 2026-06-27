import os
from loguru import logger

def get_tts_service(voice_str: str):
    """Factory to create the appropriate TTS service based on voice prefix/name.
    
    Eliminates illegal dictionary parameter errors on Turn 2 by passing only
    canonical Settings supported by each streaming provider.
    """
    voice = (voice_str or "shubh").strip()
    v_lower = voice.lower()

    if v_lower.startswith("elevenlabs:") or v_lower in ["george", "sarah", "charlie", "jessica", "eric", "chris", "brian", "laura", "roger", "neha"]:
        voice_id = voice.split(":")[-1] if ":" in voice else voice
        logger.info(f"tts_helper: Using ElevenLabs TTS | voice={voice_id}")
        from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
        return ElevenLabsTTSService(
            api_key=os.environ.get("ELEVENLABS_API_KEY", ""),
            settings=ElevenLabsTTSService.Settings(
                voice=voice_id,
                model="eleven_flash_v2_5",
            ),
        )

    elif v_lower.startswith("openai:") or v_lower in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]:
        voice_id = voice.split(":")[-1].lower() if ":" in voice else v_lower
        logger.info(f"tts_helper: Using OpenAI TTS | voice={voice_id}")
        from pipecat.services.openai.tts import OpenAITTSService
        return OpenAITTSService(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            voice=voice_id,
        )

    else:
        # Sarvam AI — pass canonical safe Settings matching known working setup
        voice_id = voice.replace("sarvam:", "").lower() if ":" in voice else v_lower
        if voice_id not in ["shubh", "bulbul", "arjun", "priya", "anushka", "kabir", "roopa", "aayan", "ashutosh", "advait", "amelia", "sophia"]:
            voice_id = "shubh"
        logger.info(f"tts_helper: Using Sarvam TTS | voice={voice_id} | model=bulbul:v3 | sample_rate=8000")
        from pipecat.services.sarvam.tts import SarvamTTSService
        return SarvamTTSService(
            api_key=os.environ.get("SARVAM_API_KEY", ""),
            sample_rate=8000,
            settings=SarvamTTSService.Settings(
                voice=voice_id,
                model="bulbul:v3",
            ),
        )

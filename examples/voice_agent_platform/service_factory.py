import os
from loguru import logger

def create_stt_service(provider: str = "deepgram", model: str = "nova-2-phonecall", language: str = "en", prewarmed: bool = True):
    provider = (provider or "deepgram").lower()
    if provider == "deepgram":
        api_key = os.environ.get("DEEPGRAM_API_KEY", "")
        if not api_key:
            logger.warning("DEEPGRAM_API_KEY is missing from environment!")
        if prewarmed:
            try:
                from prewarmed_services import PrewarmedDeepgramSTTService as DeepgramSTTService
            except ImportError:
                from pipecat.services.deepgram.stt import DeepgramSTTService
        else:
            from pipecat.services.deepgram.stt import DeepgramSTTService
            
        return DeepgramSTTService(
            api_key=api_key,
            settings=DeepgramSTTService.Settings(
                model=model or "nova-2-phonecall",
                language=language or "en",
                endpointing=200,
                utterance_end_ms=1000,
                interim_results=True,
            ),
        )
    elif provider == "sarvam":
        from pipecat.services.sarvam.stt import SarvamSTTService
        api_key = os.environ.get("SARVAM_API_KEY", "")
        if not api_key:
            logger.warning("SARVAM_API_KEY is missing from environment!")
        return SarvamSTTService(api_key=api_key, model=model or "saarika:v2")
    else:
        logger.warning(f"Unknown STT provider '{provider}', falling back to Deepgram")
        return create_stt_service("deepgram", "nova-2-phonecall", language, prewarmed)

def create_llm_service(provider: str = "openai", model: str = "gpt-4o-mini", temperature: float = 0.7):
    provider = (provider or "openai").lower()
    temp = float(temperature if temperature is not None else 0.7)
    
    if provider == "openai":
        from pipecat.services.openai.llm import OpenAILLMService
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            logger.warning("OPENAI_API_KEY is missing from environment!")
        return OpenAILLMService(
            api_key=api_key,
            settings=OpenAILLMService.Settings(model=model or "gpt-4o-mini", temperature=temp)
        )
    elif provider == "groq":
        from pipecat.services.openai.llm import OpenAILLMService
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            logger.warning("GROQ_API_KEY is missing from environment!")
        return OpenAILLMService(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            settings=OpenAILLMService.Settings(model=model or "llama-3.1-70b-versatile", temperature=temp)
        )
    elif provider == "together":
        from pipecat.services.openai.llm import OpenAILLMService
        api_key = os.environ.get("TOGETHER_API_KEY", "")
        if not api_key:
            logger.warning("TOGETHER_API_KEY is missing from environment!")
        return OpenAILLMService(
            api_key=api_key,
            base_url="https://api.together.xyz/v1",
            settings=OpenAILLMService.Settings(model=model or "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", temperature=temp)
        )
    elif provider == "anthropic":
        try:
            from pipecat.services.anthropic.llm import AnthropicLLMService
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                logger.warning("ANTHROPIC_API_KEY is missing from environment!")
            return AnthropicLLMService(
                api_key=api_key,
                model=model or "claude-3-5-sonnet-20241022",
                params=AnthropicLLMService.InputParams(temperature=temp)
            )
        except ImportError as e:
            logger.error(f"Anthropic SDK not installed ({e}), falling back to OpenAI")
            return create_llm_service("openai", "gpt-4o-mini", temp)
    else:
        logger.warning(f"Unknown LLM provider '{provider}', falling back to OpenAI")
        return create_llm_service("openai", "gpt-4o-mini", temp)

def create_tts_service(provider: str = "sarvam", voice: str = "priya", speed: float = 1.1, prewarmed: bool = True):
    provider = (provider or "sarvam").lower()
    if voice and ":" in voice:
        parts = voice.split(":", 1)
        provider = parts[0].lower() or provider
        voice = parts[1]
    pace = float(speed if speed is not None else 1.1)
    
    if provider == "sarvam":
        api_key = os.environ.get("SARVAM_API_KEY", "")
        if not api_key:
            logger.warning("SARVAM_API_KEY is missing from environment!")
        if prewarmed:
            try:
                from prewarmed_services import PrewarmedSarvamTTSService as SarvamTTSService
            except ImportError:
                from pipecat.services.sarvam.tts import SarvamTTSService
        else:
            from pipecat.services.sarvam.tts import SarvamTTSService
            
        return SarvamTTSService(
            api_key=api_key,
            settings=SarvamTTSService.Settings(
                voice_id=voice or "priya",
                model="bulbul:v3",
                pace=pace,
                min_buffer_size=30,
                max_chunk_length=150
            )
        )
    elif provider == "elevenlabs":
        from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
        api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not api_key:
            logger.warning("ELEVENLABS_API_KEY is missing from environment!")
        return ElevenLabsTTSService(
            api_key=api_key,
            settings=ElevenLabsTTSService.Settings(
                voice=voice or "21m00Tcm4TlvDq8ikWAM",
                speed=pace
            )
        )
    elif provider == "deepgram":
        from pipecat.services.deepgram.tts import DeepgramTTSService
        api_key = os.environ.get("DEEPGRAM_API_KEY", "")
        if not api_key:
            logger.warning("DEEPGRAM_API_KEY is missing from environment!")
        return DeepgramTTSService(
            api_key=api_key,
            settings=DeepgramTTSService.Settings(
                voice=voice or "aura-asteria-en"
            )
        )
    elif provider == "openai":
        from pipecat.services.openai.tts import OpenAITTSService
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            logger.warning("OPENAI_API_KEY is missing from environment!")
        return OpenAITTSService(
            api_key=api_key,
            voice=voice or "alloy",
            speed=pace
        )
    else:
        logger.warning(f"Unknown TTS provider '{provider}', falling back to Sarvam")
        return create_tts_service("sarvam", "priya", pace, prewarmed)

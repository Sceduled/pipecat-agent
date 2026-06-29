import os
from loguru import logger

def create_stt_service(provider: str = "deepgram", model: str = "nova-2-conversationalai", language: str = "en", prewarmed: bool = True, keywords: str = "", timeout: str = "500ms", eager: str = "enabled"):
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
            
        # Parse utterance end ms safely
        end_ms = 1000
        if timeout:
            try:
                end_ms = int(str(timeout).replace("ms", "").strip())
            except Exception:
                end_ms = 1000

        raw_lang = str(language).strip() if language and not isinstance(language, bool) else "en"
        if raw_lang.lower() in ["true", "false", "none", ""]:
            raw_lang = "en"
        clean_lang = raw_lang.split("-")[0].lower()

        # Map UI model strings to valid Deepgram WebSocket streaming models
        raw_model = str(model or "nova-2").lower()
        if clean_lang != "en":
            # Deepgram domain-specific models only support English on streaming WebSockets
            dg_model = "nova-2"
        elif "phonecall" in raw_model:
            dg_model = "nova-2-phonecall"
        elif "finance" in raw_model:
            dg_model = "nova-2-finance"
        elif "meeting" in raw_model:
            dg_model = "nova-2-meeting"
        elif "drivethru" in raw_model or "automotive" in raw_model:
            dg_model = "nova-2-automotive"
        else:
            # For conversational, medical, flux, or general, nova-2 is the universal streaming model
            dg_model = "nova-2"

        settings_kwargs = {
            "model": dg_model,
            "language": clean_lang,
            "endpointing": 200,
            "utterance_end_ms": end_ms,
            "interim_results": True,
        }
        if keywords and str(keywords).strip():
            kw_list = [k.strip() for k in str(keywords).split(",") if k.strip()]
            if kw_list:
                settings_kwargs["keywords"] = kw_list

        return DeepgramSTTService(
            api_key=api_key,
            settings=DeepgramSTTService.Settings(**settings_kwargs),
        )
    elif provider == "sarvam":
        from pipecat.services.sarvam.stt import SarvamSTTService
        api_key = os.environ.get("SARVAM_API_KEY", "")
        if not api_key:
            logger.warning("SARVAM_API_KEY is missing from environment!")
        return SarvamSTTService(api_key=api_key, model=model or "saarika:v2")
    else:
        logger.warning(f"Unknown STT provider '{provider}', falling back to Deepgram")
        return create_stt_service("deepgram", "nova-2", language, prewarmed)

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

def create_tts_service(provider: str = "sarvam", voice: str = "priya", speed: float = 1.1, prewarmed: bool = True, engine_model: str = "bulbul-v3"):
    provider = (provider or "sarvam").lower()
    if voice and ":" in voice:
        parts = voice.split(":", 1)
        provider = parts[0].lower() or provider
        voice = parts[1]
    pace = float(speed if speed is not None else 1.1)
    
    # Sanitize voice ID per provider so dynamic stack switches never fail with 1008 policy violations
    sarvam_voices = {"priya", "neha", "rahul", "amit", "madhav", "rohan", "kavya", "shreya", "tarun", "raghav", "advait", "gargi", "shubh", "arjun", "bulbul", "amelia", "maya"}
    openai_voices = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
    deepgram_voices = {"aura-asteria-en", "aura-luna-en", "aura-stella-en", "aura-athena-en", "aura-hera-en", "aura-orion-en", "aura-arcas-en", "aura-perseus-en", "aura-angus-en", "aura-orpheus-en", "aura-helios-en", "aura-zeus-en"}
    
    if provider == "elevenlabs":
        el_map = {
            "neha": "FGY2WhTYpPnrIDTdsKH5", # Laura (Indian Female Expressive)
            "aarav": "IKne3meq5aSn9XLyUdCD", # Charlie (Deep Confident Male)
            "priya": "EXAVITQu4vr4xnSDxMaL", # Sarah (Mature Reassuring Female)
            "rahul": "ErXwobaYiN019PkySvjV", # Antoni (Well-rounded Male)
            "rachel": "21m00Tcm4TlvDq8ikWAM",
            "sarah": "EXAVITQu4vr4xnSDxMaL",
            "laura": "FGY2WhTYpPnrIDTdsKH5",
            "charlie": "IKne3meq5aSn9XLyUdCD",
            "george": "JBFqnCBsd6RMkjVDRZzb",
            "callum": "N2lVS1w4EtoT3dr4eOWO",
            "river": "SAz9YHcvj6GT2YYXdXww",
            "harry": "SOYHLrjzK2X1ezoPC6cr",
            "liam": "TX3LPaxmHKxFdv7VOQHJ",
            "alice": "Xb7hH8MSUJpSbSDYk0k2",
            "matilda": "XrExE9yKIg1WjnnlVkGX",
            "will": "bIHbv24MWmeRgasZH58o",
            "jessica": "cgSgspJ2msm6clMCkdW9",
            "eric": "cjVigY5qzO86Huf0OWal",
            "bella": "hpp4J3VqNfWAUOO0d1Us",
            "chris": "iP95p4xoKVk53GoZ742B",
            "brian": "nPczCjzI2devNBz1zQrb",
            "daniel": "onwK4e9ZLuTAKqWW03F9",
            "lily": "pFZP5JQG7iQjIQuC4Bku",
            "adam": "pNInz6obpgDQGcFmaJgB",
            "bill": "pqHfZKP75CvOlQylNhV4",
            "roger": "CwhRBWXzGAHq8TQ4Fs17"
        }
        if str(voice).lower() in el_map:
            voice = el_map[str(voice).lower()]
        elif voice in sarvam_voices or voice in openai_voices or voice in deepgram_voices or len(str(voice)) < 15:
            voice = "21m00Tcm4TlvDq8ikWAM"
    elif provider == "sarvam":
        if str(voice).lower() not in sarvam_voices:
            voice = "priya"
    elif provider == "openai":
        if str(voice).lower() not in openai_voices:
            voice = "alloy"
    elif provider == "deepgram":
        if str(voice).lower() not in deepgram_voices and not str(voice).lower().startswith("aura-"):
            voice = "aura-asteria-en"

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
            
        sarvam_model = "bulbul:v3" if "v3" in str(engine_model or "") else "bulbul:v2"
        return SarvamTTSService(
            api_key=api_key,
            settings=SarvamTTSService.Settings(
                voice_id=voice or "priya",
                model=sarvam_model,
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
        el_model = "eleven_turbo_v2_5" if "turbo" in str(engine_model or "") else "eleven_multilingual_v2"
        return ElevenLabsTTSService(
            api_key=api_key,
            settings=ElevenLabsTTSService.Settings(
                model=el_model,
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
        oa_model = "tts-1-hd" if "hd" in str(engine_model or "") else "tts-1"
        return OpenAITTSService(
            api_key=api_key,
            model=oa_model,
            voice=voice or "alloy",
            speed=pace
        )
    else:
        logger.warning(f"Unknown TTS provider '{provider}', falling back to Sarvam")
        return create_tts_service("sarvam", "priya", pace, prewarmed)

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
            
        # Parse timeout safely
        # Deepgram requires utterance_end_ms >= 1000 (if < 1000, Deepgram returns HTTP 400 Bad Request)
        # Meanwhile, endpointing is the silence threshold in ms before turn completion (e.g. 200 to 500 ms)
        parsed_ms = 500
        if timeout:
            try:
                parsed_ms = int(str(timeout).replace("ms", "").strip())
            except Exception:
                parsed_ms = 500

        endpointing_ms = parsed_ms if parsed_ms < 1000 else 200
        utterance_end_ms = max(1000, parsed_ms) if parsed_ms >= 1000 else 1000

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
            "endpointing": endpointing_ms,
            "utterance_end_ms": utterance_end_ms,
            "interim_results": True,
        }
        if keywords and str(keywords).strip():
            kw_list = [k.strip() for k in str(keywords).split(",") if k.strip()]
            if kw_list:
                settings_kwargs["keywords"] = kw_list

        return DeepgramSTTService(
            api_key=api_key,
            sample_rate=16000,
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
    
    voice_str = str(voice).lower()
    if len(str(voice)) >= 15 and voice_str not in sarvam_voices and voice_str not in openai_voices and voice_str not in deepgram_voices:
        provider = "elevenlabs"
    elif voice_str in openai_voices and provider != "openai":
        provider = "openai"
    elif (voice_str in deepgram_voices or voice_str.startswith("aura-")) and provider != "deepgram":
        provider = "deepgram"
    elif voice_str in sarvam_voices and provider not in ("sarvam", "elevenlabs"):
        provider = "sarvam"
    
    if provider == "elevenlabs":
        el_map = {
            "qtks": "QTKSa2Iyv0yoxvXY2V8a",       # Custom voice (user's own)
            "neha": "FGY2WhTYpPnrIDTdsKH5",         # Laura (Indian Female Expressive)
            "aarav": "IKne3meq5aSn9XLyUdCD",        # Charlie (Deep Confident Male)
            "priya": "EXAVITQu4vr4xnSDxMaL",        # Sarah (Mature Reassuring Female)
            "rahul": "ErXwobaYiN019PkySvjV",         # Antoni (Well-rounded Male)
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
        voice_lower = str(voice).lower()
        if voice_lower in el_map:
            # Named alias → map to real ID
            voice = el_map[voice_lower]
        elif len(str(voice)) >= 8 and voice_lower not in sarvam_voices and voice_lower not in openai_voices and voice_lower not in deepgram_voices:
            # Raw ElevenLabs / VoiceLab ID → pass through as-is
            pass
        elif voice_lower in sarvam_voices or voice_lower in openai_voices or voice_lower in deepgram_voices:
            # Wrong-provider voice name slipped through → use safe default
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
            sample_rate=16000,
            settings=SarvamTTSService.Settings(
                voice_id=voice or "priya",
                model=sarvam_model,
                pace=pace,
                min_buffer_size=30,
                max_chunk_length=150
            )
        )
    elif provider == "elevenlabs":
        api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not api_key:
            logger.warning("ELEVENLABS_API_KEY is missing from environment!")
        if prewarmed:
            try:
                from prewarmed_services import PrewarmedElevenLabsTTSService as ElevenLabsTTSService
            except (ImportError, AttributeError):
                from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
        else:
            from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

        # Map UI model strings to valid ElevenLabs streaming models
        # eleven_multilingual_v2 is deprecated and returns HTTP 500 on new accounts
        em = str(engine_model or "").lower()
        if "flash" in em:
            el_model = "eleven_flash_v2_5"   # Fastest, cheapest, all plans
        elif "turbo" in em:
            el_model = "eleven_turbo_v2_5"   # Balanced quality/speed
        else:
            el_model = "eleven_flash_v2_5"   # Safe default (covers bulbul-v3, empty, anything else)
        # ElevenLabs premade/library voice IDs that require a paid plan via API (free tier returns isFinal=True with 0 audio on multi-stream-input)
        # Named aliases that map to these IDs (via el_map above) are also library voices
        library_voice_ids = {
            "21m00Tcm4TlvDq8ikWAM", "FGY2WhTYpPnrIDTdsKH5",
            "05ZfQq88eZ308OUIb3nk", "EXAVITQu4vr4xnSDxMaL", "IKne3meq5aSn9XLyUdCD",
            "JBFqnCBsd6RMkjVDRZzb", "N2lVS1w4EtoT3dr4eOWO", "SAz9YHcvj6GT2YYXdXww",
            "SOYHLrjzK2X1ezoPC6cr", "TX3LPaxmHKxFdv7VOQHJ", "Xb7hH8MSUJpSbSDYk0k2",
            "XrExE9yKIg1WjnnlVkGX", "bIHbv24MWmeRgasZH58o", "cgSgspJ2msm6clMCkdW9",
            "cjVigY5qzO86Huf0OWal", "hpp4J3VqNfWAUOO0d1Us", "iP95p4xoKVk53GoZ742B",
            "nPczCjzI2devNBz1zQrb", "onwK4e9ZLuTAKqWW03F9", "pFZP5JQG7iQjIQuC4Bku",
            "pNInz6obpgDQGcFmaJgB", "pqHfZKP75CvOlQylNhV4", "CwhRBWXzGAHq8TQ4Fs17",
            "ErXwobaYiN019PkySvjV",
        }

        def _find_personal_voice(key: str) -> str | None:
            """Call ElevenLabs /v1/voices and return the first personal/cloned voice ID."""
            try:
                import urllib.request, json as _json
                req = urllib.request.Request(
                    "https://api.elevenlabs.io/v1/voices",
                    headers={"xi-api-key": key, "Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=4) as resp:
                    data = _json.loads(resp.read())
                for v in data.get("voices", []):
                    if v.get("category") not in ("premade",) and v.get("voice_id") not in library_voice_ids:
                        logger.info(f"Found personal/cloned ElevenLabs voice: {v.get('name')!r} ({v.get('voice_id')})")
                        return v["voice_id"]
            except Exception as e:
                logger.warning(f"Could not list ElevenLabs voices: {e}")
            return None

        # Pick voice: passed voice (Bolna UI/config switching) -> env var -> fallback
        passed_voice = str(voice or "").strip()
        if passed_voice.lower() == "neha":
            passed_voice = "QTKSa2Iyv0yoxvXY2V8a"
        env_voice = os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
        el_voice = passed_voice if (passed_voice and passed_voice != "...") else env_voice

        # ALWAYS check: if the resolved voice is a library/premade voice, check for a personal clone
        if not el_voice or str(el_voice).strip() in library_voice_ids:
            personal = _find_personal_voice(api_key)
            if personal:
                logger.info(f"Found personal clone {personal!r} on account, using WebSocket multi-stream-input")
                el_voice = personal
            else:
                el_voice = el_voice or "QTKSa2Iyv0yoxvXY2V8a"
                logger.info(f"ElevenLabs voice {el_voice!r} is a Voice Library ID and no personal clone exists on this account. Automatically switching to ElevenLabsHttpTTSService (HTTP streaming) to bypass WebSocket 0-chunk restriction!")
                import aiohttp
                from pipecat.services.elevenlabs.tts import ElevenLabsHttpTTSService
                return ElevenLabsHttpTTSService(
                    api_key=api_key,
                    aiohttp_session=aiohttp.ClientSession(),
                    sample_rate=16000,
                    settings=ElevenLabsHttpTTSService.Settings(
                        model=el_model,
                        voice=el_voice,
                        speed=pace
                    )
                )

        logger.info(f"ElevenLabs TTS: voice={el_voice!r} model={el_model!r}")
        return ElevenLabsTTSService(
            api_key=api_key,
            sample_rate=16000,
            settings=ElevenLabsTTSService.Settings(
                model=el_model,
                voice=el_voice,
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
            sample_rate=16000,
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
            sample_rate=16000,
            model=oa_model,
            voice=voice or "alloy",
            speed=pace
        )
    else:
        logger.warning(f"Unknown TTS provider '{provider}', falling back to Sarvam")
        return create_tts_service("sarvam", "priya", pace, prewarmed)

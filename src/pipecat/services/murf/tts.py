#
# Copyright (c) 2024-2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Murf AI Text-to-Speech service integration."""

import asyncio
import base64
import io
import wave
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any, ClassVar

import aiohttp
from loguru import logger
from pydantic import BaseModel

from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    TTSAudioRawFrame,
)
from pipecat.services.settings import NOT_GIVEN, TTSSettings, _NotGiven
from pipecat.services.tts_service import TTSService
from pipecat.utils.deprecation import deprecated


@dataclass
class MurfTTSSettings(TTSSettings):
    """Settings for MurfTTSService.

    Parameters:
        modelVersion: The version of the model to use (e.g., "GEN2").
        format: The audio format to request (e.g., "WAV", "MP3", "FLAC", "ALAW", "ULAW").
    """

    modelVersion: str | None | _NotGiven = field(default_factory=lambda: NOT_GIVEN)
    format: str | None | _NotGiven = field(default_factory=lambda: NOT_GIVEN)

    _aliases: ClassVar[dict[str, str]] = {"speaker": "voice"}


class MurfTTSService(TTSService):
    """Murf AI Text-to-Speech service.

    Provides TTS synthesis using Murf AI's REST API.
    """

    Settings = MurfTTSSettings
    _settings: Settings

    @deprecated(
        "`MurfTTSService.InputParams` is deprecated since 0.0.105 and will be removed in 2.0.0. "
        "Use `MurfTTSService.Settings` instead."
    )
    class InputParams(BaseModel):
        """Configuration parameters for Murf TTS service.

        .. deprecated:: 0.0.105
            Use ``settings=MurfTTSService.Settings(...)`` instead.
            Will be removed in 2.0.0.

        Parameters:
            model_version: The version of the model to use.
            format: The audio format to request.
        """

        model_version: str | None = None
        format: str | None = None

    def __init__(
        self,
        *,
        api_key: str,
        voice_id: str | None = None,
        aiohttp_session: aiohttp.ClientSession,
        sample_rate: int | None = 24000,
        params: InputParams | None = None,
        settings: Settings | None = None,
        **kwargs,
    ):
        """Initialize Murf TTS service.

        Args:
            api_key: Murf AI API key for authentication.
            voice_id: ID of the voice to use.
            aiohttp_session: Shared aiohttp session for HTTP requests.
            sample_rate: Audio sample rate in Hz.
            params: Additional configuration parameters.
            settings: Runtime-updatable settings. When provided alongside deprecated
                parameters, ``settings`` values take precedence.
            **kwargs: Additional arguments passed to parent TTSService.
        """
        # 1. Initialize default_settings with hardcoded defaults
        default_settings = self.Settings(
            voice="en-US-natalie",
            modelVersion="GEN2",
            format="WAV",
        )

        # 2. Apply direct init arg overrides (deprecated)
        if voice_id is not None:
            self._warn_init_param_moved_to_settings("voice_id", "voice")
            default_settings.voice = voice_id

        # 3. Apply params overrides — only if settings not provided
        if params is not None:
            self._warn_init_param_moved_to_settings("params")
            if not settings:
                if params.model_version is not None:
                    default_settings.modelVersion = params.model_version
                if params.format is not None:
                    default_settings.format = params.format

        # 4. Apply settings delta (canonical API, always wins)
        if settings is not None:
            default_settings.apply_update(settings)

        super().__init__(
            sample_rate=sample_rate,
            push_stop_frames=True,
            push_start_frame=True,
            settings=default_settings,
            **kwargs,
        )

        self._api_key = api_key
        self._session = aiohttp_session
        self._base_url = "https://api.murf.ai/v1/speech/generate"

    def can_generate_metrics(self) -> bool:
        """Check if this service can generate processing metrics.

        Returns:
            True, as Murf REST service supports metrics generation.
        """
        return True

    def _build_payload(self, text: str) -> dict[str, Any]:
        """Build the JSON payload for the Murf API request."""
        payload: dict[str, Any] = {
            "text": text,
            "voiceId": self._settings.voice,
            "encodeAsBase64": True,
        }

        if self._settings.modelVersion is not None:
            payload["modelVersion"] = self._settings.modelVersion

        if self._settings.format is not None:
            payload["format"] = self._settings.format

        if self._settings.language is not None and self._settings.language != NOT_GIVEN:
            payload["locale"] = str(self._settings.language)

        return payload

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame | None, None]:
        """Generate speech from text using Murf AI REST API.

        Args:
            text: The text to convert to speech.
            context_id: Unique identifier for this TTS context.

        Yields:
            Frame: Audio frames containing the synthesized speech.
        """
        logger.debug(f"{self}: Generating TTS [{text}]")
        try:
            payload = self._build_payload(text)
            headers = {"api-key": self._api_key, "Content-Type": "application/json"}

            await self.start_ttfb_metrics()

            for attempt in range(3):
                async with self._session.post(self._base_url, json=payload, headers=headers) as r:
                    if r.status != 200:
                        error_text = await r.text()
                        error_msg = f"Murf AI API error: {r.status} {error_text}"
                        if attempt == 2:
                            logger.error(error_msg)
                            yield ErrorFrame(error=error_msg)
                            return
                        logger.warning(error_msg + f". Retrying {attempt+1}/3...")
                        await asyncio.sleep(0.5)
                        continue

                    data = await r.json()

                    # Murf API returns audio in 'encodedAudio' (base64 WAV);
                    # 'audioFile' is a legacy URL field and is always None.
                    audio_b64 = data.get("encodedAudio") or data.get("audioFile")
                    if not audio_b64:
                        if attempt == 2:
                            error_msg = f"Murf AI API returned success but no audio data. Response keys: {list(data.keys())}"
                            logger.error(error_msg)
                            yield ErrorFrame(error=error_msg)
                            return
                        logger.warning(
                            f"Murf API returned 200 but missing audio. Response keys: {list(data.keys())}. "
                            f"Retrying {attempt+1}/3..."
                        )
                        await asyncio.sleep(0.5)
                        continue

                    break

            if audio_b64.startswith("data:audio"):
                audio_b64 = audio_b64.split(",")[1]

            audio_bytes = base64.b64decode(audio_b64)

            wav_sample_rate = self.sample_rate
            wav_channels = 1

            if self._settings.format == "WAV" or self._settings.format == "wav":
                try:
                    with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                        wav_sample_rate = wf.getframerate()
                        wav_channels = wf.getnchannels()
                        audio_bytes = wf.readframes(wf.getnframes())
                except Exception as e:
                    logger.warning(f"{self}: Failed to parse WAV header, yielding raw bytes: {e}")

            await self.start_tts_usage_metrics(text)

            # ~0.1s chunks (16-bit PCM = 2 bytes per sample)
            chunk_size = int(wav_sample_rate * 0.1) * 2 * wav_channels
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i : i + chunk_size]
                if len(chunk) > 0:
                    if i == 0:
                        await self.stop_ttfb_metrics()
                    frame = TTSAudioRawFrame(
                        audio=chunk, sample_rate=wav_sample_rate, num_channels=wav_channels
                    )
                    yield frame

        except Exception as e:
            logger.exception(f"{self}: Error generating TTS: {e}")
            yield ErrorFrame(error=str(e))

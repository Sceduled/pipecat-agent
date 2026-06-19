#
# Copyright (c) 2024-2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Vobiz WebSocket audio streaming serializer for Pipecat.

Vobiz streams bidirectional G.711 µ-law audio over WebSocket using a
JSON envelope protocol. Docs: https://docs.vobiz.ai/concepts/streaming-websockets
"""

import base64
import json

from loguru import logger

from pipecat.audio.dtmf.types import KeypadEntry
from pipecat.audio.utils import create_stream_resampler, pcm_to_ulaw, ulaw_to_pcm
from pipecat.frames.frames import (
    AudioRawFrame,
    CancelFrame,
    EndFrame,
    Frame,
    InputAudioRawFrame,
    InputDTMFFrame,
    InterruptionFrame,
    OutputTransportMessageFrame,
    OutputTransportMessageUrgentFrame,
    StartFrame,
)
from pipecat.serializers.base_serializer import FrameSerializer


class VobizFrameSerializer(FrameSerializer):
    """Serializer for the Vobiz WebSocket audio streaming protocol.

    Converts between Pipecat frames and Vobiz's JSON WebSocket messages.
    Audio is G.711 µ-law at 8 kHz, base64-encoded inside JSON envelopes.

    StreamSid and CallSid are auto-populated from the ``start`` event, so
    they do not need to be passed at construction time. Pass them explicitly
    only when you pre-parse the start event yourself (e.g., from a runner
    helper that reads the first two messages before building the pipeline).

    Unlike Twilio/Plivo there is no Vobiz REST API for forced hang-up. The
    call ends when the WebSocket closes, so ``auto_hang_up`` simply lets the
    transport layer close the connection on ``EndFrame`` / ``CancelFrame``
    without emitting any extra message.

    Example::

        serializer = VobizFrameSerializer()

        @app.event_handler("on_connected")
        async def on_connected(service, frame):
            ...
    """

    class InputParams(FrameSerializer.InputParams):
        """Configuration parameters for VobizFrameSerializer.

        Parameters:
            vobiz_sample_rate: Sample rate used by Vobiz. Always 8000 Hz (G.711).
            sample_rate: Override pipeline input sample rate (defaults to StartFrame value).
            auto_hang_up: Log and signal end-of-call on EndFrame/CancelFrame.
        """

        vobiz_sample_rate: int = 8000
        sample_rate: int | None = None
        auto_hang_up: bool = True

    def __init__(
        self,
        stream_sid: str = "",
        call_sid: str | None = None,
        params: "VobizFrameSerializer.InputParams | None" = None,
    ):
        """Initialize the VobizFrameSerializer.

        Args:
            stream_sid: Vobiz StreamSid. Populated automatically from the ``start``
                event if left empty (the common case).
            call_sid: Vobiz CallSid. Populated automatically from the ``start`` event.
            params: Optional configuration overrides.
        """
        params = params or VobizFrameSerializer.InputParams()
        super().__init__(params)
        self._params: VobizFrameSerializer.InputParams = params

        self._stream_sid = stream_sid
        self._call_sid = call_sid

        self._vobiz_sample_rate = self._params.vobiz_sample_rate
        self._sample_rate = 0  # Set from StartFrame

        self._input_resampler = create_stream_resampler()
        self._output_resampler = create_stream_resampler()

    # ------------------------------------------------------------------
    # FrameSerializer interface
    # ------------------------------------------------------------------

    async def setup(self, frame: StartFrame) -> None:
        """Capture pipeline sample rate from StartFrame.

        Args:
            frame: The StartFrame containing pipeline audio configuration.
        """
        self._sample_rate = self._params.sample_rate or frame.audio_in_sample_rate

    async def serialize(self, frame: Frame) -> str | bytes | None:
        """Convert a Pipecat frame to a Vobiz WebSocket message.

        Args:
            frame: Frame to serialize.

        Returns:
            JSON string ready to send over the WebSocket, or ``None`` to skip.
        """
        if self._params.auto_hang_up and isinstance(frame, (EndFrame, CancelFrame)):
            # Vobiz ends the call when the WebSocket closes; no REST API needed.
            logger.debug(f"VobizFrameSerializer: end-of-call ({type(frame).__name__}), closing.")
            return None

        if isinstance(frame, InterruptionFrame):
            return json.dumps({"event": "clearAudio", "streamId": self._stream_sid})

        if isinstance(frame, AudioRawFrame):
            serialized_audio = await pcm_to_ulaw(
                frame.audio,
                frame.sample_rate,
                self._vobiz_sample_rate,
                self._output_resampler,
            )
            if not serialized_audio:
                return None

            payload = base64.b64encode(serialized_audio).decode("utf-8")
            return json.dumps(
                {
                    "event": "playAudio",
                    "media": {
                        "contentType": "audio/x-mulaw",
                        "sampleRate": self._vobiz_sample_rate,
                        "payload": payload,
                    },
                }
            )

        if isinstance(frame, (OutputTransportMessageFrame, OutputTransportMessageUrgentFrame)):
            if self.should_ignore_frame(frame):
                return None
            return json.dumps(frame.message)

        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        """Convert a Vobiz WebSocket message to a Pipecat frame.

        Auto-populates ``stream_sid`` and ``call_sid`` from the ``start`` event
        so callers do not need to pass them at construction.

        Args:
            data: Raw WebSocket text received from Vobiz.

        Returns:
            A Pipecat frame, or ``None`` for events that need no pipeline action.
        """
        logger.trace(f"VobizFrameSerializer: RAW IN type={type(data).__name__} data={str(data)[:200]!r}")

        try:
            message = json.loads(data)
        except json.JSONDecodeError:
            logger.warning(f"VobizFrameSerializer: invalid JSON: {data!r}")
            return None

        event = message.get("event")
        if event is None:
            logger.warning(f"VobizFrameSerializer: no 'event' key in message: {message}")

        if event == "connected":
            logger.debug("VobizFrameSerializer: WebSocket connected")
            return None

        if event == "start":
            self._stream_sid = message.get("streamId", self._stream_sid)
            self._call_sid = message.get("callId", self._call_sid)
            logger.info(
                f"VobizFrameSerializer: call started — "
                f"streamId={self._stream_sid} callId={self._call_sid}"
            )
            return None

        if event == "media":
            media = message.get("media", {})
            # Only process inbound (caller → server) audio; skip echoed outbound track.
            if media.get("track") == "outbound":
                return None
            payload_b64 = media.get("payload")
            if not payload_b64:
                return None

            ulaw_bytes = base64.b64decode(payload_b64)
            pcm = await ulaw_to_pcm(
                ulaw_bytes,
                self._vobiz_sample_rate,
                self._sample_rate,
                self._input_resampler,
            )
            if not pcm:
                return None

            return InputAudioRawFrame(audio=pcm, num_channels=1, sample_rate=self._sample_rate)

        if event == "dtmf":
            digit = message.get("dtmf", {}).get("digit")
            if digit:
                try:
                    return InputDTMFFrame(KeypadEntry(digit))
                except ValueError:
                    logger.warning(f"VobizFrameSerializer: unknown DTMF digit: {digit!r}")
            return None

        if event == "stop":
            logger.info(
                f"VobizFrameSerializer: call stopped — StreamSid={self._stream_sid}"
            )
            return None

        return None

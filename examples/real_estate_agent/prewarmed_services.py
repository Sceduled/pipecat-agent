import asyncio
from loguru import logger
from starlette.websockets import WebSocketState as State
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.sarvam.tts import SarvamTTSService

class PrewarmedDeepgramSTTService(DeepgramSTTService):
    """Deepgram STT service that prevents duplicate connection loops when pre-warmed."""
    async def _connect(self):
        if getattr(self, "_connection_task", None) is not None:
            logger.debug(f"{self}: Reusing pre-warmed Deepgram connection task")
            return
        await super()._connect()

class PrewarmedSarvamTTSService(SarvamTTSService):
    """Sarvam TTS service that gracefully checks existing open WebSocket connections."""
    async def _connect(self):
        if getattr(self, "_websocket", None) is not None and self._websocket.state is State.OPEN:
            logger.debug(f"{self}: Reusing pre-warmed Sarvam WebSocket connection")
            return
        await super()._connect()

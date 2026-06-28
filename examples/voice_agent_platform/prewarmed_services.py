import asyncio
from loguru import logger
from websockets.protocol import State
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.utils.asyncio.task_manager import TaskManager, TaskManagerParams

def _init_task_manager(service):
    try:
        loop = asyncio.get_event_loop()
        tm = TaskManager()
        tm.setup(TaskManagerParams(loop=loop))
        service._task_manager = tm
    except Exception as e:
        logger.warning(f"Could not early-init TaskManager: {e}")

class PrewarmedDeepgramSTTService(DeepgramSTTService):
    """Deepgram STT service that prevents duplicate connection loops when pre-warmed."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _init_task_manager(self)

    async def _connect(self):
        if getattr(self, "_connection_task", None) is not None:
            logger.debug(f"{self}: Reusing pre-warmed Deepgram connection task")
            return
        await super()._connect()

class PrewarmedSarvamTTSService(SarvamTTSService):
    """Sarvam TTS service that gracefully checks existing open WebSocket connections."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _init_task_manager(self)

    async def _connect(self):
        if getattr(self, "_websocket", None) is not None and self._websocket.state is State.OPEN:
            logger.debug(f"{self}: Reusing pre-warmed Sarvam WebSocket connection")
            return
        await super()._connect()

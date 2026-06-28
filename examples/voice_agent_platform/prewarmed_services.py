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

    async def _connection_handler(self):
        from pipecat.services.deepgram.stt import EventType
        retries = 0
        while True:
            connect_kwargs = self._build_connect_kwargs()
            keepalive_task = None
            try:
                async with self._client.listen.v1.connect(**connect_kwargs) as connection:
                    retries = 0
                    self._connection = connection
                    self._connection_ready.set()
                    connection.on(EventType.MESSAGE, self._on_message)
                    connection.on(EventType.ERROR, self._on_error)

                    logger.debug(f"{self}: Websocket connection initialized")

                    keepalive_task = self.create_task(
                        self._keepalive_handler(), f"{self}::keepalive"
                    )
                    await connection.start_listening()
            except asyncio.CancelledError:
                break
            except Exception as e:
                retries += 1
                err_str = str(e)
                if "400" in err_str or "401" in err_str or "403" in err_str or retries >= 3:
                    logger.error(f"{self}: Fatal WebSocket error or max retries reached ({err_str}). Stopping retry loop.")
                    break
                logger.warning(f"{self}: Connection lost, retry #{retries} in 1s: {e}")
                await asyncio.sleep(1.0)
            finally:
                self._connection_ready.clear()
                self._connection = None
                if keepalive_task:
                    await self.cancel_task(keepalive_task)

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

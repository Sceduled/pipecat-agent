# syntax=docker/dockerfile:1
FROM python:3.12-slim

# System deps for audio processing (resampy, soxr, onnxruntime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first (layer cache)
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Install pipecat with required extras
RUN uv sync --no-dev \
    --extra deepgram \
    --extra groq \
    --extra sarvam \
    --extra websocket \
    && uv pip install "uvicorn[standard]" aiohttp python-dotenv sqlalchemy psycopg2-binary

# Copy the voice agent platform
COPY examples/voice_agent_platform/ ./examples/voice_agent_platform/

ENV PORT=8080
EXPOSE 8080

WORKDIR /app/examples/voice_agent_platform
CMD ["uv", "run", "python", "main.py"]

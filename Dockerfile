# syntax=docker/dockerfile:1

# Stage 1: Build the frontend dashboard
FROM node:20-slim AS frontend-build
WORKDIR /app
COPY examples/voice_agent_platform/dashboard/package*.json ./
RUN npm ci
COPY examples/voice_agent_platform/dashboard/ ./
RUN npm run build

# Stage 2: Python backend
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

# Copy the built dashboard from the frontend stage
COPY --from=frontend-build /app/dist ./examples/voice_agent_platform/dashboard/dist

ENV PORT=8080
EXPOSE 8080

WORKDIR /app/examples/voice_agent_platform
CMD ["uv", "run", "python", "main.py"]

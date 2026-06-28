# Kakkamutta Platform: Technical Overview & Features

## 1. Executive Summary
The Kakkamutta Platform is a full-stack, multimodal Conversational AI platform. It provides a visual interface (Dashboard) for managing, configuring, and deploying real-time voice agents. The system integrates Large Language Models (LLMs), Speech-to-Text (STT), Text-to-Speech (TTS), and SIP telephony to create autonomous agents capable of conducting human-like conversations over the phone.

---

## 2. System Architecture
The platform is built on a modern, decoupled architecture:

- **Frontend (Control Plane):** A React/Vite Single Page Application (SPA) utilizing Framer Motion for advanced UI/UX and glassmorphism design. It communicates with the backend via REST APIs.
- **Backend (Data Plane):** A Python FastAPI server that handles HTTP API requests from the dashboard and manages WebSocket connections for real-time audio streaming.
- **AI Orchestration (Pipecat):** The core conversational engine is powered by Pipecat, an open-source framework for building real-time voice pipelines. It handles Voice Activity Detection (VAD), turn-taking, and interruption handling.
- **Database:** A PostgreSQL relational database (hosted on Railway) using SQLAlchemy ORM to store agent configurations, phone number mappings, and historical call logs.
- **Telephony & Media:** Vobiz handles the SIP-to-WebSocket bridging, connecting traditional PSTN phone calls to our backend audio streams.

---

## 3. Dashboard Features & Capabilities
The React Dashboard serves as the central command center for the platform, offering several key features:

### A. Agent Builder & Configuration
Users can create multiple distinct "Agents" with unique configurations:
- **System Prompts:** Define the agent's persona, objective (e.g., booking an appointment), and behavioral guardrails.
- **Voice Selection:** Select from provider-specific TTS voices (e.g., Priya, Bulbul, Arjun) to match the use case.
- **Knowledge Base (RAG):** Users can upload context (via text or file extraction) that the agent uses to ground its responses, allowing it to answer company-specific FAQs or reference pricing accurately.

### B. Inbound & Outbound Routing
- **Inbound Mapping:** Users can assign specific DIDs (Phone Numbers) to specific agents. When the backend receives an inbound call, it queries the database to load the correct agent configuration associated with the dialed number.
- **Outbound Dialer:** Users can manually trigger outbound calls directly from the dashboard UI, injecting dynamic lead data (e.g., the customer's name) into the agent's context window.

### C. Call Logging & Transcripts
Every completed call is recorded in the PostgreSQL database. The dashboard provides a "Call Logs" view where users can review:
- The timestamp and direction (Inbound/Outbound) of the call.
- The associated agent and customer phone number.
- The **Full Call Transcript**, allowing managers to audit the AI's performance and review conversation details.

---

## 4. The Conversational AI Pipeline Workflow
When a phone call is established, the following real-time, ultra-low-latency pipeline is executed:

1. **SIP Initiation:** The customer dials the number. Vobiz accepts the SIP invite and opens a bi-directional WebSocket connection to the FastAPI backend.
2. **Context Aggregation:** The backend fetches the agent's configuration (System Prompt, Knowledge Base) from PostgreSQL and initializes the LLM context window.
3. **Speech-to-Text (Deepgram):** As the customer speaks, incoming audio frames are streamed to Deepgram for real-time transcription.
4. **Language Model (OpenAI/ChatGPT):** The transcribed text is appended to the context window. The LLM processes the conversation history and streams back a text-based response token-by-token.
5. **Text-to-Speech (Sarvam/ElevenLabs):** The text tokens are piped directly into the TTS provider, which synthesizes human-like audio frames.
6. **Audio Playback:** The synthesized audio frames are pushed down the pipeline, through the WebSocket, and played back to the user over the phone network.

*Note: The pipeline utilizes Voice Activity Detection (VAD) to actively monitor the user's speech. If the user interrupts the AI while it is speaking, the pipeline immediately halts the TTS audio buffer and listens to the user, creating a natural conversational dynamic.*

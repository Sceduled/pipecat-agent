# Deep-Architecture Build Prompts: Pipecat SaaS Platform

*These prompts are highly engineered for Claude or any advanced coding agent. They include deep architectural constraints, error handling, and directory structures to ensure nothing breaks as you scale from a single agent to a Bolna-like platform.*

---

## 🛠️ Phase 1: Multilingual Outbound Sandbox (Hindi-First)
*Goal: Create an isolated Hindi-first code-switching agent without touching production routing.*

**Copy and paste this prompt:**
> "We are implementing Phase 1: Multilingual Outbound Sandbox. Our goal is to test Hindi/English code-switching securely without risking our existing outbound agent.
> 
> **Architecture & Tasks:**
> 1. **Duplicate & Isolate:** Copy `outbound_agent.py` to a new file named `multilingual_outbound_agent.py`. In this new file, rename the runner to `run_multilingual_outbound()`. Crucially, create a new, isolated dictionary: `pending_multilingual_sessions = {}` so state does not leak between agents.
> 2. **Hindi-First Prompt Engineering:** Update `_BASE_RULES` in the new file. Add this exact constraint: *'Your primary language is Hindi. Speak in natural conversational Hindi using Latin script (e.g. "Haa, bilkul, main samajh rahi hu"). You MUST start the conversation in Hindi. If and only if the user speaks to you in English, you may switch to English. Otherwise, default to Hindi.'*
> 3. **Safe Routing in `main.py`:** Add three new endpoints:
>    - `POST /dial-multilingual`: Copies the logic of `/dial` but saves the context to `pending_multilingual_sessions` and points `answer_url` to `/voice-xml/outbound-multilingual`.
>    - `GET /voice-xml/outbound-multilingual`: Returns VoiceXML pointing to `/ws/outbound-multilingual`.
>    - `@app.websocket('/ws/outbound-multilingual')`: Accepts the WebSocket and triggers `run_multilingual_outbound()`.
> 4. **Validation:** Ensure all existing routes (`/dial`, `/ws/outbound`) remain completely untouched. Add robust try/except blocks around the new WebSocket handler to prevent server crashes. Commit and push when done."

---

## 🖥️ Phase 2: Configuration API & Local Dashboard MVP
*Goal: Build a Vite/React UI to edit prompts dynamically via a JSON store with rock-solid fallback logic.*

**Copy and paste this prompt:**
> "We are implementing Phase 2: Configuration API & Local Dashboard MVP. Our goal is to build a UI to configure our agent, ensuring the Pipecat pipeline never crashes if the config is missing.
> 
> **Architecture & Tasks:**
> 1. **Data Layer (`config_manager.py`):** Create this file to handle reading/writing `agent_config.json`. Use `pydantic` to define an `AgentConfig` model (fields: `system_prompt`, `voice`, `enabled_tools`). Implement a `get_config()` method that attempts to load the JSON. **CRITICAL:** If the file doesn't exist or is invalid, it MUST return a hardcoded default config object containing our current working prompt and the 'priya' voice.
> 2. **Backend APIs (`main.py`):** Add `GET /api/config` and `POST /api/config` to interface with `config_manager.py`. Add `CORSMiddleware` to FastAPI allowing `http://localhost:5173` so the UI can connect.
> 3. **Pipeline Injection:** Refactor `inbound_agent.py` and `outbound_agent.py`. Instead of hardcoded strings, call `config_manager.get_config()`. Inject `config.system_prompt` into `OpenAILLMService.Settings` and `config.voice` into `SarvamTTSService.Settings`. This guarantees zero downtime if the UI breaks.
> 4. **Frontend UI (`dashboard/`):** Run `npx create-vite dashboard --template react`. Install `lucide-react`. Build a premium, glassmorphic UI using Vanilla CSS (vibrant gradients, blurred panels). The UI must have:
>    - A large `textarea` for the System Prompt.
>    - A `<select>` dropdown for Voice ('priya', 'bulbul').
>    - A 'Save Changes' button that POSTs to `/api/config` and shows a success toast.
> 5. **Validation:** Document exactly how to run the Vite dev server alongside the FastAPI server in a `DASHBOARD_README.md`. Commit and push."

---

## 🗄️ Phase 3: Multi-Tenant Database & Dynamic Agent Routing
*Goal: Evolve the platform into a Bolna-like SaaS where users can create multiple distinct agents.*

**Copy and paste this prompt:**
> "We are implementing Phase 3: Multi-Tenant SaaS Routing. Our goal is to transition from a single JSON config to a relational database supporting unlimited custom agents.
> 
> **Architecture & Tasks:**
> 1. **Database Setup (`database.py`):** Initialize SQLAlchemy with SQLite (for now). Create an `Agent` table with columns: `id` (String UUID), `name` (String), `system_prompt` (Text), `voice` (String), `created_at` (DateTime). 
> 2. **Refactoring the UI:** Update the React dashboard to be multi-tenant. Add a sidebar listing all agents (fetched from `GET /api/agents`). Add a 'Create New Agent' button. The main configuration panel should now edit the selected agent via `PUT /api/agents/{id}`.
> 3. **Outbound Routing (`main.py` & `outbound_agent.py`):** 
>    - Modify the `POST /dial` payload to require an `"agent_id"`.
>    - Store the `agent_id` inside the `pending_outbound_sessions` dictionary alongside the lead data.
>    - In `ws_outbound()`, extract the `agent_id` from the session context, fetch that specific Agent from the DB, and pass its `system_prompt` and `voice` as explicit arguments into `run_outbound(..., system_prompt, voice)`.
> 4. **Inbound Routing:** Create a new DB table `PhoneNumbers` (columns: `phone_number`, `agent_id`). When Vobiz hits `/voice-xml/inbound`, check the HTTP headers or query params for the dialed `To` number, look up the `agent_id` in the DB, and append it to the WS url: `ws://.../ws/inbound?agent_id={id}`.
> 5. **Validation:** Ensure that if an invalid `agent_id` is passed, the WebSocket immediately closes with a 4004 error code rather than crashing the Pipecat runner. Commit and push."

---

## 📊 Phase 4: Call Logs, Analytics & Recordings
*Goal: Provide total visibility into agent performance via transcripts and audio recordings in the UI.*

**Copy and paste this prompt:**
> "We are implementing Phase 4: Observability and Call Logs. Our goal is to capture the conversation transcript and audio recording for every call and display it beautifully in the dashboard.
> 
> **Architecture & Tasks:**
> 1. **Database Schema:** Create a `CallLog` table (columns: `id`, `agent_id`, `lead_phone`, `direction` (inbound/outbound), `transcript` (JSON), `recording_url` (String), `outcome` (String), `created_at`).
> 2. **Capturing the Transcript:** In `inbound_agent.py` and `outbound_agent.py`, update the `on_client_disconnected` event handler. Before destroying the worker, call `context.get_messages()` to extract the entire conversation history. Save this JSON directly to the `CallLog` table.
> 3. **Handling Call Outcomes:** Update the `update_call_outcome` python tool. Instead of just logging to the console, it must UPDATE the `CallLog` row for the current call with the outcome string (e.g., 'visit_booked'). 
> 4. **Vobiz Webhook for Audio:** Add a `POST /webhook/vobiz-recording` endpoint to `main.py`. When Vobiz completes a call, it sends the recording URL here. Look up the `CallLog` by phone number/time and save the `recording_url`.
> 5. **Dashboard Analytics UI:** In the React app, build a 'Call History' page. Fetch data from `GET /api/agents/{id}/logs`. Display a sleek data table showing Date, Phone, Direction, and Outcome. When a row is clicked, open a slide-out panel that contains an HTML5 `<audio>` player for the `recording_url` and a chat-bubble UI mapping over the `transcript` JSON to show the AI vs Human conversation.
> 6. **Validation:** Ensure async DB writes do not block the Pipecat pipeline shutdown sequence. Commit and push."

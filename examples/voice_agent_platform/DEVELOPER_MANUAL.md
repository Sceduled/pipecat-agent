# Kakkamutta Platform - Developer Manual

Welcome to the Kakkamutta Platform repository! This project is a full-stack AI Voice Agent Builder that allows you to create, configure, and monitor conversational AI agents (Inbound, Outbound, and Multilingual).

## 🏗️ Architecture Overview
This project is split into two main parts:
1. **The Backend (Python/FastAPI & Pipecat):** Located in the root of `examples/real_estate_agent`. This handles the WebSocket connections to the SIP provider (Vobiz), the LLM logic, and the database.
2. **The Frontend (React & Vite):** Located in `examples/real_estate_agent/dashboard`. This is the glassmorphism UI where you build the agents and view call logs.
3. **The Database:** A PostgreSQL database hosted on Railway that stores Agent configurations, Phone Number mappings, and Call Logs (including full transcripts).

---

## 🚀 1. Running the Dashboard (Frontend) Locally
You can run the React dashboard on your laptop without needing to spin up the Python backend. The local dashboard is configured to automatically point to the live Production API on Railway (`kakkamutta-production.up.railway.app`).

**Steps:**
1. Clone the repository:
   ```bash
   git clone https://github.com/Sceduled/pipecat-agent.git
   cd pipecat-agent/examples/real_estate_agent/dashboard
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
4. Open your browser to `http://localhost:5173`. Any changes you make to the `.jsx` or `.css` files will hot-reload instantly.

---

## ☁️ 2. Deploying Code Updates
Deployment is 100% automated via GitHub Actions and Railway!

Whenever you want to push a new feature, fix a bug, or update the UI, all you have to do is push your code to the `main` branch:

```bash
git add .
git commit -m "Added a new feature"
git push origin main
```

**What happens next?**
1. Railway detects the push to GitHub.
2. Railway automatically pulls the new code and builds it.
3. If you added new database columns (in `database.py`), the `auto_migrate()` function runs on boot to update the live PostgreSQL database.
4. Within ~60 seconds, your code is live in production!

---

## 🛠️ 3. Running the Backend (Python) Locally
If you are developing new Pipecat features or debugging the LLM pipeline, you may want to run the backend locally instead of testing in production.

> [!WARNING]
> **API Keys Required:** To run the backend locally, you must ask the project owner to securely send you the `.env` file. It contains the highly sensitive keys for OpenAI, Deepgram, and Sarvam. **Never commit the `.env` file to GitHub.**

**Steps:**
1. Place the `.env` file inside `examples/real_estate_agent/`.
2. Install `uv` (the Python package manager used in this project) if you haven't already.
3. Sync the dependencies:
   ```bash
   uv sync
   ```
4. Start the backend server:
   ```bash
   uv run python main.py
   ```
5. The local backend will now be running on `http://localhost:8000`.

*Note: If you run the backend locally, you will need to update `dashboard/src/App.jsx` to point `API_BASE` to `http://localhost:8000/api` so your local frontend talks to your local backend.*

---

## 📁 Key Files to Know
- `main.py`: The FastAPI server that handles API requests, WebSockets, and database routing.
- `database.py`: The SQLAlchemy ORM models (Agent, PhoneNumber, CallLog). Add new database columns here and update `auto_migrate()`.
- `inbound_agent.py` & `outbound_agent.py`: The Pipecat worker pipelines that handle the actual conversational AI logic, VAD (Voice Activity Detection), and turn management.
- `dashboard/src/App.jsx`: The monolithic React frontend containing the UI layout, Framer Motion animations, and API calls.
- `dashboard/src/index.css`: The massive stylesheet containing the animated mesh gradient and glassmorphism design system.

# 🎛️ Agent Configuration Dashboard

This is a local, React-based dashboard built to dynamically configure your Pipecat Voice Agent's persona and voice, exactly like a SaaS platform UI.

## How to Run It

To use the dashboard, you need to run **both** the FastAPI server and the Vite React server at the same time.

### 1. Start the FastAPI Backend
Open your first terminal window and navigate to the agent directory:
```bash
cd examples/real_estate_agent
uvicorn main:app --port 8080 --reload
```

### 2. Start the Vite Frontend
Open a **second** terminal window and run:
```bash
cd examples/real_estate_agent/dashboard
npm run dev
```

### 3. Open the Dashboard
Navigate to `http://localhost:5173` in your browser. 
Any changes you make here will be instantly saved to `agent_config.json`. Because we built a dynamic injection layer, the Pipecat agent will read this file the very next time you place a call!

## Safety Guarantees
If you make a mistake in the UI, or if the `agent_config.json` file is deleted, **your production server will not crash**. The backend has a Pydantic safety net that will silently fall back to a default hardcoded configuration.

import json
import os
from database import SessionLocal, Agent, PhoneNumber

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "agent_config.json")

def seed():
    db = SessionLocal()
    
    # Check if we already have agents
    if db.query(Agent).count() > 0:
        print("Database already has agents.")
        db.close()
        return

    system_prompt = """You are Priya, an AI sales agent for Prestige Realty.
You speak clearly and warmly. Keep responses concise."""
    voice = "priya"

    # Try to load from the old config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                system_prompt = data.get("system_prompt", system_prompt)
                voice = data.get("voice", voice)
        except Exception:
            pass

    # Create the default agent
    default_agent = Agent(
        name="Prestige Realty Default Agent",
        system_prompt=system_prompt,
        voice=voice
    )
    db.add(default_agent)
    db.commit()
    db.refresh(default_agent)
    
    print(f"Seeded default agent: {default_agent.name} with ID: {default_agent.id}")
    db.close()

if __name__ == "__main__":
    seed()

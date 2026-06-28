import os
from database import SessionLocal, Agent

def update_agent_voice():
    db = SessionLocal()
    agent = db.query(Agent).first()
    if agent:
        print(f"Current voice: {agent.voice}")
        agent.voice = "shubh"
        
        # We also reset system_prompt to ensure it has the outbound directive we wanted
        # in case it was overwritten via dashboard
        base_prompt = """You are Shubh, an AI sales agent for Prestige Realty.
You speak clearly and warmly. Keep responses extremely brief (1-2 short sentences maximum). 
Maintain a natural, confident, and modern tone. 
Absolutely NO backend commentary, NO long explanations, and NO robotic phrasing.

CRITICAL: THIS IS AN OUTBOUND CALL. YOU ARE THE ONE CALLING THE USER.
You MUST act like the initiator of the call. 
Do NOT ask "How can I help you today?". 
Instead, state the reason you are calling and politely ask if they have a minute."""
        
        agent.system_prompt = base_prompt
        db.commit()
        print("Updated voice back to shubh and restored outbound system prompt.")
    else:
        print("No agent found in DB.")
    db.close()

if __name__ == "__main__":
    update_agent_voice()

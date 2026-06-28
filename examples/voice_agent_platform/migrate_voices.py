import sys
import os
sys.path.append(os.path.dirname(__file__))

from database import SessionLocal, Agent

def migrate():
    db = SessionLocal()
    agents = db.query(Agent).all()
    count = 0
    for agent in agents:
        modified = False
        if agent.voice == "priya":
            agent.voice = "shubh"
            modified = True
            
        if "priya" in agent.system_prompt.lower() or "warm" in agent.system_prompt.lower():
            # Simply replace priya with shubh
            import re
            # case insensitive replacement
            new_prompt = re.sub(r'(?i)you are priya', 'You are Shubh', agent.system_prompt)
            new_prompt = re.sub(r'(?i)a warm', 'a confident and knowledgeable', new_prompt)
            
            if new_prompt != agent.system_prompt:
                agent.system_prompt = new_prompt
                modified = True
                
        if modified:
            count += 1
            
    db.commit()
    print(f"Migrated {count} agents in the database.")
    db.close()

if __name__ == "__main__":
    migrate()

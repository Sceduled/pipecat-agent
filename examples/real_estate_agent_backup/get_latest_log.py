import sys
import os
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.path.dirname(__file__))

from database import SessionLocal, CallLog

def get_latest_log():
    db = SessionLocal()
    # Get the most recent call log
    log = db.query(CallLog).order_by(CallLog.created_at.desc()).first()
    if log:
        print(f"Call ID: {log.id}")
        print(f"Agent ID: {log.agent_id}")
        print(f"Direction: {log.direction}")
        print(f"Duration: {log.duration}s")
        print(f"Outcome: {log.outcome}")
        print("Transcript:")
        print(log.transcript)
    else:
        print("No call logs found.")
    db.close()

if __name__ == "__main__":
    get_latest_log()

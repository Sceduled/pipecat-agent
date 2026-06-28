import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "agents.db")
    engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

class Agent(Base):
    __tablename__ = "agents"
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    niche = Column(String, nullable=False, default="custom")
    company_name = Column(String, nullable=False, default="")
    knowledge_base = Column(Text, nullable=False, default="")
    agent_type = Column(String, nullable=False, default="inbound")
    system_prompt = Column(Text, nullable=False)
    voice = Column(String, nullable=False, default="priya")
    
    # Zero-code multi-provider switching columns
    stt_provider = Column(String, nullable=False, default="deepgram")
    stt_model = Column(String, nullable=False, default="nova-2-phonecall")
    llm_provider = Column(String, nullable=False, default="openai")
    llm_model = Column(String, nullable=False, default="gpt-4o-mini")
    llm_temperature = Column(Float, nullable=False, default=0.7)
    tts_provider = Column(String, nullable=False, default="sarvam")
    tts_voice = Column(String, nullable=False, default="priya")
    tts_speed = Column(Float, nullable=False, default=1.1)
    opener_text = Column(Text, nullable=False, default="Hi {{lead_name}}, I'm calling from {{company_name}}. Do you have a moment to chat?")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    phone_numbers = relationship("PhoneNumber", back_populates="agent", cascade="all, delete-orphan")
    call_logs = relationship("CallLog", back_populates="agent", cascade="all, delete-orphan")

class PhoneNumber(Base):
    __tablename__ = "phone_numbers"
    phone_number = Column(String, primary_key=True) # e.g. +1234567890
    agent_id = Column(String, ForeignKey("agents.id"))
    
    agent = relationship("Agent", back_populates="phone_numbers")

class CallLog(Base):
    __tablename__ = "call_logs"
    id = Column(String, primary_key=True, default=generate_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    direction = Column(String, nullable=False) # "inbound" or "outbound"
    caller_number = Column(String, nullable=False)
    transcript = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    agent = relationship("Agent", back_populates="call_logs")

Base.metadata.create_all(bind=engine)

from sqlalchemy import text
def auto_migrate():
    queries = [
        "ALTER TABLE agents ADD COLUMN agent_type VARCHAR NOT NULL DEFAULT 'inbound'",
        "ALTER TABLE agents ADD COLUMN niche VARCHAR NOT NULL DEFAULT 'custom'",
        "ALTER TABLE agents ADD COLUMN company_name VARCHAR NOT NULL DEFAULT ''",
        "ALTER TABLE agents ADD COLUMN knowledge_base TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE call_logs ADD COLUMN transcript TEXT",
        "ALTER TABLE agents ADD COLUMN stt_provider VARCHAR NOT NULL DEFAULT 'deepgram'",
        "ALTER TABLE agents ADD COLUMN stt_model VARCHAR NOT NULL DEFAULT 'nova-2-phonecall'",
        "ALTER TABLE agents ADD COLUMN llm_provider VARCHAR NOT NULL DEFAULT 'openai'",
        "ALTER TABLE agents ADD COLUMN llm_model VARCHAR NOT NULL DEFAULT 'gpt-4o-mini'",
        "ALTER TABLE agents ADD COLUMN llm_temperature FLOAT NOT NULL DEFAULT 0.7",
        "ALTER TABLE agents ADD COLUMN tts_provider VARCHAR NOT NULL DEFAULT 'sarvam'",
        "ALTER TABLE agents ADD COLUMN tts_voice VARCHAR NOT NULL DEFAULT 'priya'",
        "ALTER TABLE agents ADD COLUMN tts_speed FLOAT NOT NULL DEFAULT 1.1",
        "ALTER TABLE agents ADD COLUMN opener_text TEXT NOT NULL DEFAULT 'Hi {{lead_name}}, I''m calling from {{company_name}}. Do you have a moment to chat?'"
    ]
    for q in queries:
        try:
            with engine.begin() as conn:
                conn.execute(text(q))
        except Exception:
            pass

auto_migrate()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_agent(agent_id: str):
    db = SessionLocal()
    try:
        return db.query(Agent).filter(Agent.id == agent_id).first()
    finally:
        db.close()

import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey
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
    created_at = Column(DateTime, default=datetime.utcnow)
    
    phone_numbers = relationship("PhoneNumber", back_populates="agent")
    call_logs = relationship("CallLog", back_populates="agent")

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
    created_at = Column(DateTime, default=datetime.utcnow)
    
    agent = relationship("Agent", back_populates="call_logs")

Base.metadata.create_all(bind=engine)

from sqlalchemy import text
def auto_migrate():
    try:
        with engine.begin() as conn:
            try:
                conn.execute(text("ALTER TABLE agents ADD COLUMN agent_type VARCHAR NOT NULL DEFAULT 'inbound'"))
            except Exception: pass
            try:
                conn.execute(text("ALTER TABLE agents ADD COLUMN niche VARCHAR NOT NULL DEFAULT 'custom'"))
            except Exception: pass
            try:
                conn.execute(text("ALTER TABLE agents ADD COLUMN company_name VARCHAR NOT NULL DEFAULT ''"))
            except Exception: pass
            try:
                conn.execute(text("ALTER TABLE agents ADD COLUMN knowledge_base TEXT NOT NULL DEFAULT ''"))
            except Exception: pass
    except Exception as e:
        print("Auto-migration failed:", e)

auto_migrate()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

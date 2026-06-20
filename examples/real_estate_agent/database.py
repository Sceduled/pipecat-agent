import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

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
    system_prompt = Column(Text, nullable=False)
    voice = Column(String, nullable=False, default="priya")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    phone_numbers = relationship("PhoneNumber", back_populates="agent")

class PhoneNumber(Base):
    __tablename__ = "phone_numbers"
    phone_number = Column(String, primary_key=True) # e.g. +1234567890
    agent_id = Column(String, ForeignKey("agents.id"))
    
    agent = relationship("Agent", back_populates="phone_numbers")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

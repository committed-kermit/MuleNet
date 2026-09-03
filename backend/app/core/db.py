from sqlmodel import SQLModel, create_engine, Session
from app.config import settings
import sqlite3

# SQLite engine with WAL mode for fast concurrent reads & writes
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)

def init_db():
    # Enable WAL mode
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
        conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

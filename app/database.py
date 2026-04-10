import os

from sqlmodel import Session, SQLModel, create_engine

DB_URL = os.getenv("DB_URL", "sqlite:///./rescue_center.db")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

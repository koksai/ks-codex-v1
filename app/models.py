from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str
    username: str = Field(index=True, unique=True)
    password_hash: str
    role: str = Field(default="officer")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CaseRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    case_code: str = Field(index=True, unique=True)
    title: str
    description: str
    status: str = Field(default="open")
    reporter_name: str
    created_by: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Incident(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    details: str
    latitude: float
    longitude: float
    severity: str = Field(default="high")
    reported_by: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Notification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    message: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    is_read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

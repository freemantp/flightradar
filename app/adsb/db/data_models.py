from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field


class Position(BaseModel):
    lat: float
    lon: float
    alt: Optional[int] = None
    timestmp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expire_at: Optional[datetime] = None

    def __repr__(self):
        return f'pos=({self.lat},{self.lon},{self.alt}) at={self.timestmp}'

    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }


class Flight(BaseModel):
    callsign: Optional[str] = None
    modeS: str
    is_military: bool = False
    first_contact: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_contact: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expire_at: Optional[datetime] = None

    def __str__(self):
        return f'Flight modeS={self.modeS}, callsign={self.callsign} [{"mil" if self.is_military else "civ"}], last_contact={self.last_contact}'

    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }


class IncompleteAircraft(BaseModel):
    modeS: str
    query_attempts: int = 0
    sources_queried: List[str] = Field(default_factory=list)
    expire_at: Optional[datetime] = None

    def __str__(self):
        return f'UnknownAircraft modeS={self.modeS}, attempts={self.query_attempts}'

    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }

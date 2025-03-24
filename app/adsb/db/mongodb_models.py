from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Position(BaseModel):
    lat: float
    lon: float
    alt: Optional[int] = None
    timestmp: datetime = Field(default_factory=datetime.utcnow)

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
    archived: bool = False
    first_contact: datetime = Field(default_factory=datetime.utcnow)
    last_contact: datetime = Field(default_factory=datetime.utcnow)

    def __str__(self):
        return f'Flight modeS={self.modeS}, callsign={self.callsign} [{"mil" if self.is_military else "civ"}], archived={self.archived}, last_contact={self.last_contact}'

    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }

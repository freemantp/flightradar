from sqlmodel import SQLModel, Field, Relationship, create_engine
from typing import Optional, List
import datetime
from os import path
from sqlalchemy import text

class Flight(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    callsign: Optional[str] = None
    modeS: str = Field(index=True, max_length=6)
    is_military: bool = Field(default=False)
    archived: bool = Field(default=False)
    first_contact: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    last_contact: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    
    # Relationships
    positions: List["Position"] = Relationship(back_populates="flight")
    
    def __str__(self):
        return f'Flight id={self.id}, callsign={self.callsign}, modeS={self.modeS} [{"mil" if self.is_military else "civ"}], archived={self.archived}, last_contact={self.last_contact}'

class Position(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    flight_id: int = Field(foreign_key="flight.id")
    lat: float
    lon: float
    alt: Optional[int] = None
    timestmp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    
    # Relationships
    flight: Flight = Relationship(back_populates="positions")
    
    def __repr__(self):
        return f'flight={self.flight_id} pos=({self.lat},{self.lon},{self.alt}) at={self.timestmp}'

DB_MODEL_CLASSES = [Flight, Position]

def init_schema(engine):
    SQLModel.metadata.create_all(engine)
    
    # Create trigger to update flight last_contact
    with engine.connect() as conn:
        conn.execute(text(
            """
            CREATE TRIGGER IF NOT EXISTS flight_timestmp_trigger 
            AFTER INSERT ON position 
            BEGIN 
                UPDATE flight SET last_contact = NEW.timestmp 
                WHERE id=NEW.flight_id; 
            END
            """
        ))
        conn.commit()

def init_db(data_folder):
    db_path = path.join(data_folder, 'flights.sqlite')
    
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )
    
    return engine
from .dbmodels import Position, Flight
from sqlmodel import Session, select, func
from datetime import datetime, timedelta
from itertools import zip_longest
from typing import List, Dict, Tuple, Any


class DBRepository:

    @staticmethod
    def split_flights(positions):
        """ Splits position data from positions into 'flights' and returns them as lists"""
        flights = []

        if positions:
            fifteen_min = timedelta(minutes=15)
            current_flight_id = positions[0].flight_id
            start_idx = 0

            for i in range(1, len(positions)):
                tdiff = positions[i].timestmp - positions[i-1].timestmp
                if abs(tdiff) > fifteen_min or positions[i].flight_id != current_flight_id:
                    flights.append(positions[start_idx:i])
                    start_idx = i
                    current_flight_id = positions[i].flight_id

            flights.append(positions[start_idx:])
        return flights

    @staticmethod
    def get_flights(session: Session, modeS_addr: str) -> List[Flight]:
        statement = select(Flight).where(Flight.modeS == modeS_addr)
        return session.exec(statement).all()

    @staticmethod
    def flight_exists(session: Session, flight_id: int) -> bool:
        statement = select(Flight).where(Flight.id == flight_id)
        return session.exec(statement).first() is not None

    @staticmethod
    def get_all_positions(session: Session, is_archived: bool = False) -> Dict[str, List[Tuple[float, float, int]]]:
        statement = (
            select(Flight.modeS, Position.lat, Position.lon, Position.alt)
            .join(Position, Position.flight_id == Flight.id)
            .where(Flight.archived == is_archived)
            .order_by(Position.flight_id, Position.timestmp)
        )

        positions_map = {}
        results = session.exec(statement).all()

        for modeS, lat, lon, alt in results:
            if modeS not in positions_map:
                positions_map[modeS] = []
            positions_map[modeS].append((lat, lon, alt))

        return positions_map

    @staticmethod
    def get_positions(session: Session, flight_id: int) -> List[Position]:
        statement = (
            select(Position)
            .where(Position.flight_id == flight_id)
            .order_by(Position.timestmp)
        )
        return session.exec(statement).all()

    @staticmethod
    def get_recent_flights_last_pos(db_session: Session, min_timestamp=datetime.min) -> List[Tuple[Position, Flight]]:
        """ Retrieves flights with their most recent position. 
        Only flights with activity newer than the passed timestamp will be considered"""

        # First get latest position timestamp for each flight
        subquery = (
            select(
                Position.flight_id,
                func.max(Position.timestmp).label("max_timestmp")
            )
            .group_by(Position.flight_id)
            .subquery()
        )

        # Then join to get the position records and flight details
        statement = (
            select(Position, Flight)
            .join(Flight, Position.flight_id == Flight.id)
            .join(
                subquery,
                (Position.flight_id == subquery.c.flight_id) &
                (Position.timestmp == subquery.c.max_timestmp)
            )
            .where(Flight.last_contact > min_timestamp)
        )

        return db_session.exec(statement).all()

    @staticmethod
    def get_non_archived_flights_older_than(session: Session, timestamp: datetime) -> List[Flight]:
        statement = (
            select(Flight)
            .where((Flight.last_contact < timestamp) & (Flight.archived == False))
        )
        return session.exec(statement).all()

    @staticmethod
    def delete_flights_and_positions(session: Session, flight_ids: List[int]):
        assert (len(flight_ids) > 0)

        for ids_chunk in DBRepository._get_chunks(flight_ids, 200):
            # Filter out None values added by zip_longest
            ids = [id for id in ids_chunk if id is not None]

            # Delete positions first (due to foreign key constraint)
            positions_to_delete = session.exec(
                select(Position).where(Position.flight_id.in_(ids))
            ).all()
            for position in positions_to_delete:
                session.delete(position)
            
            # Then delete flights
            flights_to_delete = session.exec(
                select(Flight).where(Flight.id.in_(ids))
            ).all()
            for flight in flights_to_delete:
                session.delete(flight)
            
            session.commit()

    @staticmethod
    def _get_chunks(iterable, chunk_size):
        args = [iter(iterable)] * chunk_size
        return zip_longest(*args, fillvalue=None)

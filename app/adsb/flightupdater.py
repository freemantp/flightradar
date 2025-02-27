import logging

from time import sleep
from datetime import datetime, timedelta
from timeit import default_timer as timer
from typing import List

from .datasource.modesmixer import ModeSMixer
from .datasource.virtualradarserver import VirtualRadarServer
from .datasource.dump1090 import Dump1090
from .util.modes_util import ModesUtil
from .db.dbmodels import Position, Flight
from .db.dbrepository import DBRepository
from ..config import Config
from .model.position_report import PositionReport
# from playhouse.sqliteq import ResultTimeout

from .util.logging import LOGGER_NAME

logger = logging.getLogger('Updater')


class FlightUpdater:

    MINUTES_BEFORE_CONSIDRERED_NEW_FLIGHT = 10

    def initialize(self, config):

        self.sleep_time = 1
        self._t = None

        if config.RADAR_SERVICE_TYPE == 'mm2':
            self._service = ModeSMixer(config.RADAR_SERVICE_URL)
        elif config.RADAR_SERVICE_TYPE == 'vrs':
            self._service = VirtualRadarServer(config.RADAR_SERVICE_URL)
        elif config.RADAR_SERVICE_TYPE == 'dmp1090':
            self._service = Dump1090(config.RADAR_SERVICE_URL)
        else:
            raise ValueError('Service type not specified in config')

        self._mil_ranges = ModesUtil(config.DATA_FOLDER)
        self._mil_only = config.MILTARY_ONLY
        self.interrupted = False

        # see https://stackoverflow.com/questions/35616602/peewee-operationalerror-too-many-sql-variables-on-upsert-of-only-150-rows-8-c#36788489
        self._insert_batch_size = 50
        self._delete_after = config.DB_RETENTION_MIN

        # Lookup stuctures
        self.modeS_flightid_map = dict()
        self.flight_lastpos_map = dict()
        self.flight_last_contact = dict()
        self._initialize_from_db()

    def is_service_alive(self):
        return self._service.connection_alive

    def get_cached_flights(self) -> List[PositionReport]:

        timestamp = datetime.utcnow() - timedelta(minutes=1)

        return {v: self.flight_lastpos_map.get(v)
                for (k, v) in self.modeS_flightid_map.items()
                if v in self.flight_lastpos_map and self.flight_last_contact[v] > timestamp}

    def cleanup_items(self):
        if self._delete_after > 0:
            from sqlmodel import Session
            from ..config import app_state
            
            delete_timestamp = datetime.utcnow() - timedelta(minutes=self._delete_after)
            
            with Session(app_state.db_engine) as session:
                flights_to_delete = DBRepository.get_non_archived_flights_older_than(session, delete_timestamp)

                if flights_to_delete:
                    # Delete from DB
                    flight_ids = [f.id for f in flights_to_delete]
                    DBRepository.delete_flights_and_positions(session, flight_ids)
                    
                    # Update cache
                    for flight in flights_to_delete:
                        self.modeS_flightid_map.pop(flight.modeS, None)
                        self.flight_lastpos_map.pop(flight.id, None)
                        self.flight_last_contact.pop(flight.id, None)
                    
                    deleted_msg = ', '.join(['{:d} (cs={})'.format(f.id, f.callsign) for f in flights_to_delete])
                    logger.info(f'aircraftEvent=delete {deleted_msg}')

    def _threshold_timestamp(self):
        return datetime.utcnow() - timedelta(minutes=self.MINUTES_BEFORE_CONSIDRERED_NEW_FLIGHT)

    def _initialize_from_db(self):
        """ Initializes cache from database """

        from sqlmodel import Session
        from ..config import app_state
        
        recent_flight_timestamp = datetime.utcnow() - timedelta(minutes=self.MINUTES_BEFORE_CONSIDRERED_NEW_FLIGHT)

        with Session(app_state.db_engine) as session:
            results = DBRepository.get_recent_flights_last_pos(session, recent_flight_timestamp)
            
            for pos, flight in results:
                self.modeS_flightid_map[flight.modeS] = flight.id
                # TODO: add track to dbModel
                self.flight_lastpos_map[flight.id] = PositionReport(
                    flight.modeS, pos.lat, pos.lon, pos.alt, 0.0, flight.callsign)
                self.flight_last_contact[flight.id] = flight.last_contact

    def update(self):

        start_time = timer()
        positions = self._service.query_live_flights(False)
        end_service_time = timer()
        flight_end_time = timer()
        pos_end_time = timer()

        try:
            if positions:

                # Filter for military modeS
                filtered_pos = [pos for pos in positions if self._mil_ranges.is_military(
                    pos.icao24)] if self._mil_only else positions

                # Update flights
                self.update_flights(filtered_pos)
                flight_end_time = timer()

                # Add non-empty positions
                self.add_positions([p for p in filtered_pos if p.lat and p.lon])
                pos_end_time = timer()

            self.cleanup_items()

        # except ResultTimeout:
        #     logger.error('Database timeout')
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            logger.exception("An error occured")

        end_time = timer()
        execution_time = timedelta(seconds=end_time-start_time)

        if execution_time > timedelta(seconds=0.5):
            service_delta = timedelta(seconds=end_service_time-start_time)
            db_delta = timedelta(seconds=end_time-end_service_time)
            flight_delta = timedelta(seconds=flight_end_time-end_service_time)
            pos_delta = timedelta(seconds=pos_end_time-flight_end_time)

            timing_info = {'total_time_ms': execution_time.total_seconds() * 1000,
                           'db_time_ms': db_delta.total_seconds() * 1000,
                           'service_time_ms': service_delta.total_seconds() * 1000
                           }

            logger.info('Flight data processing time total={:.2f}ms, service={:.2f}ms'.format(
                timing_info['total_time_ms'], timing_info['service_time_ms']), extra=timing_info)

    def add_positions(self, positions: List[PositionReport]):
        """ Inserts positions into the database"""
        from sqlmodel import Session
        from ..config import app_state
        
        # Create position objects for DB insertion
        positions_to_insert = []

        for pos in positions:
            flight_id = self.modeS_flightid_map[pos.icao24]
            
            # If position is the same as last time, filter it
            if flight_id not in self.flight_lastpos_map or (flight_id in self.flight_lastpos_map and self.flight_lastpos_map[flight_id] != pos):
                self.flight_last_contact[flight_id] = datetime.utcnow()
                self.flight_lastpos_map[flight_id] = pos
                
                # Create position object
                position = Position(
                    flight_id=flight_id,
                    lat=pos.lat,
                    lon=pos.lon,
                    alt=pos.alt
                )
                positions_to_insert.append(position)

        # Insert new positions in batches
        if positions_to_insert:
            with Session(app_state.db_engine) as session:
                for i in range(0, len(positions_to_insert), self._insert_batch_size):
                    batch = positions_to_insert[i:i+self._insert_batch_size]
                    session.add_all(batch)
                    session.commit()

    def update_flights(self, flights: List[PositionReport]):
        """ Inserts and updates flights in the database"""
        from sqlmodel import Session, select
        from ..config import app_state
        
        inserted_flights = []
        updated_flights = []
        
        # create a new flight even if other flights in db match modes/callsign, but too much time elapsed since last position report
        thresh_timestmp = self._threshold_timestamp()
        
        with Session(app_state.db_engine) as session:
            for f in flights:
                # Check if we have a recent flight with this modeS
                statement = (
                    select(Flight)
                    .where(Flight.modeS == f.icao24, Flight.last_contact > thresh_timestmp)
                )
                flight_result = session.exec(statement).first()
                
                if flight_result:
                    # Update existing flight if needed
                    if f.callsign and not flight_result.callsign:
                        flight_result.callsign = f.callsign
                        session.add(flight_result)
                        session.commit()
                        updated_flights.append((f.icao24, f.callsign))
                    
                    # Update in-memory map
                    if not f.icao24 in self.modeS_flightid_map:
                        self.modeS_flightid_map[f.icao24] = flight_result.id
                else:
                    # Create new flight
                    new_flight = Flight(
                        modeS=f.icao24,
                        callsign=f.callsign,
                        is_military=self._mil_ranges.is_military(f.icao24)
                    )
                    session.add(new_flight)
                    session.commit()
                    session.refresh(new_flight)
                    
                    # Update in-memory map
                    self.modeS_flightid_map[f.icao24] = new_flight.id
                    inserted_flights.append((f.icao24, f.callsign))

        if inserted_flights:
            inserted_msg = ', '.join(['{} (cs={})'.format(f[0], f[1]) for f in inserted_flights])
            logger.info('aircraftEvent=insert {:s}'.format(inserted_msg))

        if updated_flights:
            updated_msg = ', '.join(['{} (cs={})'.format(f[0], f[1]) for f in updated_flights])
            logger.info('aircraftEvent=update {:s}'.format(updated_msg))

    def insert_flight(self, icao24, callsign):

        from flask import current_app as app
        is_military = app.modes_util.is_military(icao24)

        flight_id = Flight.insert(modeS=icao24, callsign=callsign, is_military=is_military).execute()
        self.modeS_flightid_map[icao24] = flight_id

    def update_callsign(self, callsign, flight_id):
        Flight.update(callsign=callsign).where(Flight.id == flight_id).execute()

    def get_silhouete_params(self):
        return self._service.get_silhouete_params()

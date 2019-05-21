import logging

from time import sleep
from datetime import datetime, timedelta
from timeit import default_timer as timer

from ..util.singleton import Singleton

from .datasource.modesmixer import ModeSMixer
from .datasource.virtualradarserver import VirtualRadarServer
from .util.modes_util import ModesUtil
from .db.dbmodels import Position, Flight, database_proxy as db
from .db.dbrepository import DBRepository
from ..config import Config

from peewee import IntegrityError
from playhouse.sqliteq import ResultTimeout

from .util.logging import LOGGER_NAME

logger = logging.getLogger('Updater')

#TODO: Why singleton?
@Singleton
class FlightUpdater(object):

    MINUTES_BEFORE_CONSIDRERED_NEW_FLIGHT = 10

    def initialize(self, config):

        self.sleep_time = 1
        self._t = None

        if config.RADAR_SERVICE_TYPE == 'mm2':
            self._service = ModeSMixer(config.RADAR_SERVICE_URL)
        elif config.RADAR_SERVICE_TYPE == 'vrs':
            self._service = VirtualRadarServer(config.RADAR_SERVICE_URL)
        else:
            raise ValueError('Service type not specified in config')

        self._mil_ranges = ModesUtil(config.DATA_FOLDER)
        self._mil_only = config.MILTARY_ONLY
        self.interrupted = False

        # see https://stackoverflow.com/questions/35616602/peewee-operationalerror-too-many-sql-variables-on-upsert-of-only-150-rows-8-c#36788489
        self._insert_batch_size = 50
        self._delete_after = config.DB_RETENTION_MIN

        # Lookup stuctures
        self.modeS_flight_map = dict()
        self.flight_lastpos_map = dict()
        self._initialize_from_db()

    def is_service_alive(self):
        return self._service.connection_alive

    def get_cached_flights(self):
        return { k:self.flight_lastpos_map.get(v) for (k,v) in self.modeS_flight_map.items() if v in self.flight_lastpos_map }

    def cleanup_items(self):

        if self._delete_after > 0:
            
            delete_timestamp = datetime.utcnow() - timedelta(minutes=self._delete_after)

            with db.atomic() as transaction:            
                for flight in DBRepository.get_non_archived_flights_older_than(delete_timestamp):
                    DBRepository.delete_flight_and_positions(flight.id)
                    self.modeS_flight_map.pop(flight.modeS, None)
                    self.flight_lastpos_map.pop(flight.id, None)
                    logger.debug('Deleted flight {:s} (id={:d})'.format(
                        str(flight.callsign), flight.id))

    def _threshold_timestamp(self):
        return datetime.utcnow() - timedelta(minutes=self.MINUTES_BEFORE_CONSIDRERED_NEW_FLIGHT)

    def _initialize_from_db(self):

        recent_flight_timestamp = datetime.utcnow() - timedelta(minutes=self.MINUTES_BEFORE_CONSIDRERED_NEW_FLIGHT)
        
        for pos_flights in DBRepository.get_recent_flights_last_pos(recent_flight_timestamp):
            self.modeS_flight_map[pos_flights.flight_fk.modeS] = pos_flights.flight_fk.id
            self.flight_lastpos_map[pos_flights.flight_fk.id] = (pos_flights.flight_fk.id, pos_flights.lat, pos_flights.lon, pos_flights.alt )

    def update(self):

        start_time = timer()
        positions = self._service.query_live_flights(False)
        end_service_time = timer()
        flight_end_time = timer()
        pos_end_time = timer()

        try:
            if positions:

                # Filter for military icaos
                filtered_pos = [pos for pos in positions if self._mil_ranges.is_military(
                    pos[0])] if self._mil_only else positions

                # Update flights
                self.update_flights(filtered_pos)
                flight_end_time = timer()

                # Add non-empty positions
                self.add_positions([p for p in filtered_pos if p[1] and p[2]])
                pos_end_time = timer()

            self.cleanup_items()

        except ResultTimeout:
            logger.info('Database timeout')
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            logger.exception("An error occured")

        end_time = timer()
        execution_time = timedelta(seconds=end_time-start_time)

        if execution_time > timedelta(seconds=1):

            service_delta = timedelta(seconds=end_service_time-start_time)
            db_delta = timedelta(seconds=end_time-end_service_time)
            flight_delta = timedelta(seconds=flight_end_time-end_service_time)
            pos_delta = timedelta(seconds=pos_end_time-flight_end_time)

            logger.warn('Took {:.2f}s to process flight data [db={:.2f}s, fl={:.2f}, pos={:.2f} service={:.2f}s] '
                .format(execution_time.total_seconds(), db_delta.total_seconds(), flight_delta.total_seconds(), pos_delta.total_seconds(), service_delta.total_seconds()))

    def add_positions(self, positions):
        """ Inserts positions into the database"""

        # Create tuples suitable for DB insertion
        db_tuples = [(self.modeS_flight_map[p[0]], p[1], p[2], p[3]) for p in positions]

        # If position is the same as last time, filter it
        db_tuples = [t for t in db_tuples 
                      if t[0] not in self.flight_lastpos_map 
                      or (t[0] in self.flight_lastpos_map and self.flight_lastpos_map[t[0]] != t)]

        for tpl in db_tuples:
            self.flight_lastpos_map[tpl[0]] = tpl

        # Insert new
        if db_tuples:
            fields = [Position.flight_fk, Position.lat,
                      Position.lon, Position.alt]

            with db.atomic() as transaction:
                for i in range(0, len(db_tuples), self._insert_batch_size):
                    Position.insert_many(
                        db_tuples[i:i+self._insert_batch_size], fields=fields).execute()

    def update_flights(self, flights):
        """ Inserts and updates  flights in the database"""

        with db.atomic() as transaction:

            # (modeS, callsign), None for a callsign is allowed
            for modeS_callsgn in  [(f[0], f[4]) for f in flights]:

                # create a new flight even if other flights in db match modes/callsign, but too much time elapsed since last position report
                thresh_timestmp = self._threshold_timestamp()

                if modeS_callsgn[0] in self.modeS_flight_map:

                    flight_result = (Flight.select(Flight.id)
                                    .where(Flight.modeS == modeS_callsgn[0], Flight.last_contact > thresh_timestmp))

                    if flight_result:
                        if modeS_callsgn[1]:
                            self.update_callsign(modeS_callsgn[1], flight_result[0].id)
                            logger.info('updated callsign: modeS:{} -> {}'.format(modeS_callsgn[0], modeS_callsgn[1]))
                    else:
                        logger.warn('should not happen: {}'.format(str(modeS_callsgn)))
                        #self.insert_flight(modeS_callsgn)

                else:

                    flight_result = (Flight.select(Flight.id)
                                    .where(Flight.modeS == modeS_callsgn[0], Flight.callsign == modeS_callsgn[1], Flight.last_contact > thresh_timestmp))
                    if flight_result:
                        # just update map if recent flight present in db
                        self.modeS_flight_map[modeS_callsgn[0]] = flight_result[0].id
                    else:
                        self.insert_flight(modeS_callsgn)
                        logger.info('inserted {} ({})'.format(modeS_callsgn[1] if modeS_callsgn[1] else '', modeS_callsgn[0]))

    def insert_flight(self, modeS_callsgn):
        flight_id = Flight.insert(modeS=modeS_callsgn[0], callsign=modeS_callsgn[1]).execute()
        self.modeS_flight_map[modeS_callsgn[0]] = flight_id


    def update_callsign(self, callsign, flight_id):
        Flight.update(callsign=callsign).where(Flight.id == flight_id).execute() 
    

    def get_silhouete_params(self):
        return self._service.get_silhouete_params()

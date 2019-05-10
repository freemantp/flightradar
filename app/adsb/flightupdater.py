from threading import Timer
from time import sleep
import datetime
import logging

from ..util.singleton import Singleton

from .datasource.modesmixer import ModeSMixer
from .datasource.virtualradarserver import VirtualRadarServer
from .util.modes_util import ModesUtil
from .db.dbmodels import Position, Flight
from .db.dbrepository import DBRepository
from ..config import Config

from flask import current_app

from peewee import IntegrityError
from playhouse.sqliteq import ResultTimeout

from .util.logging import LOGGER_NAME

logger = logging.getLogger('Updater')

@Singleton
class FlightUpdater(object):

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
        self.interrupted = False
        self._mil_only = config.MILTARY_ONLY
        self.delete_after = config.DB_RETENTION_MIN
        self.modeS_flight_map = dict()
        # see https://stackoverflow.com/questions/35616602/peewee-operationalerror-too-many-sql-variables-on-upsert-of-only-150-rows-8-c#36788489
        self._insert_batch_size = 50

    def is_service_alive(self):
        return self._service.connection_alive

    def cleanup_items(self):

        if self.delete_after > 0:
            delete_timestamp = datetime.datetime.utcnow() - datetime.timedelta(minutes=self.delete_after)

            for flight in DBRepository.get_non_archived_flights_older_than(delete_timestamp):
                DBRepository.delete_flight_and_positions(flight.id)
                logger.debug('Deleted flight {:s} (id={:d})'.format(str(flight.callsign), flight.id))

            # TODO: Cleanup modeS_flight_map as well!

    def _run(self):

        positions = self._service.query_live_flights(False)

        try:
            if positions:

                # Filter for military icaos
                filtered_pos = [pos for pos in positions if self._mil_ranges.is_military(pos[0])] if self._mil_only else positions
                
                # Update flights
                self.update_flights(filtered_pos)

                # Add non-empty positions
                self.add_positions([p for p in filtered_pos if p[1] and p[2]])

            self.cleanup_items()

        except ResultTimeout:
            logger.info('Database timeout')
        except:
            logger.exception("An error occured")

        self._t = Timer(self.sleep_time, self._run)
        self._t.start()

    def add_positions(self, position_array):

        """ Inserts positions into the database"""

        # Create tuples suitable for DB insertion
        db_entries = [(self.modeS_flight_map[m[0]], m[1], m[2], m[3]) for m in position_array]

        # Insert new
        if db_entries:
            fields = [Position.flight_fk, Position.lat, Position.lon, Position.alt]
            for i in range(0, len(db_entries), self._insert_batch_size):
                Position.insert_many(db_entries[i:i+self._insert_batch_size], fields=fields).execute()
        
    def update_flights(self, flights):

        """ Updates flights in the database"""

        # None for a callsign is allowed
        active_flights = [ (f[0], f[4]) for f in flights] # (modeS, callsign)

        for modeS_callsgn in active_flights:

            # create a new flight even if other flights in db match modes/callsign, but too much time elapsed since last position report
            thresh_timestmp = datetime.datetime.utcnow() - datetime.timedelta(minutes=10) 

            if modeS_callsgn[0] in self.modeS_flight_map:

                flight_results = (Flight.select(Flight.id)
                        .where(Flight.modeS == modeS_callsgn[0], Flight.last_contact > thresh_timestmp))
   
                if flight_results and modeS_callsgn[1]:                    
                    Flight.update(callsign = modeS_callsgn[1]).where(Flight.id == flight_results[0].id).execute()
                    logger.info('updated {:s} ({:s})'.format(modeS_callsgn[1] if modeS_callsgn[1] else "None" ,modeS_callsgn[0]))
                else:
                    #logger.warning('A new flight should have been inserted')
                    pass
            
            else:

                flight_results = (Flight.select(Flight.id)
                        .where(Flight.modeS == modeS_callsgn[0], Flight.callsign == modeS_callsgn[1], Flight.last_contact > thresh_timestmp))
   
                if flight_results:
                    flight_id = flight_results[0].id
                    logger.info('present in db {:s} ({:s})'.format(modeS_callsgn[1] if modeS_callsgn[1] else "None", modeS_callsgn[0]))
                else:
                    flight_id = Flight.insert(modeS=modeS_callsgn[0], callsign=modeS_callsgn[1] ).execute()
                    logger.info('inserted {:s} ({:s})'.format(modeS_callsgn[1] if modeS_callsgn[1] else "None", modeS_callsgn[0] ))

                self.modeS_flight_map[modeS_callsgn[0]] = flight_id

    def start(self):
        if self._t is None:
            self._t = Timer(self.sleep_time, self._run)
            self._t.start()
        else:
            raise Exception("this timer is already running")

    def stop(self):
        if self._t is not None:
            self._t.cancel()
            self._t = None

    def isAlive(self):
        return self._t.isAlive()

    def get_silhouete_params(self):
        return self._service.get_silhouete_params()

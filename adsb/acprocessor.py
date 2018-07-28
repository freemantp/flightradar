from threading import Timer
from time import sleep
import datetime
import logging

from adsb.datasource.modesmixer import ModeSMixer
from adsb.datasource.virtualradarserver import VirtualRadarServer
from adsb.util.modes_util import ModesUtil
from adsb.db.dbmodels import Position, Flight
from adsb.db.dbrepository import DBRepository

from peewee import IntegrityError
from playhouse.sqliteq import ResultTimeout

logger = logging.getLogger(__name__)

class AircaftProcessor(object):

    def __init__(self, config, db):

        self.sleep_time = 1
        self._t = None

        if config.type == 'mm2':
            self._service = ModeSMixer(config.service_url)
        elif config.type == 'vrs':
            self._service = VirtualRadarServer(config.service_url)
        else:
            raise ValueError('Service type not specified in config')

        self._mil_ranges = ModesUtil(config.data_folder)
        self.interrupted = False
        self._mil_only = config.military_only
        self._db = db
        self.delete_after = config.delete_after
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
                logger.info('Deleted flight {:s} (id={:d})'.format(str(flight.callsign), flight.id))

    def _run(self):

        positions = self._service.query_live_positions()        

        try:
            if positions:
                # Filter for military icaos
                if self._mil_only:
                    filtered_pos = filter(lambda p : self._mil_ranges.is_military(p[0]), positions)
                else:
                    filtered_pos = positions
                    #filtered_pos = list(filter(lambda p : self._mil_ranges.is_swiss(p[0]), positions))

                self.update_callsigns(filtered_pos)

                # Filter sempty positons
                non_empty_pos = filter(lambda p : p[1] and p[2], filtered_pos)
                pos_array = list(non_empty_pos)

                # Creatr tuples suitable for DB insertion
                db_entries = list(map(lambda m : (self.modeS_flight_map[m[0]], m[1], m[2], m[3]), pos_array))

                if db_entries:
                    fields = [Position.flight_fk, Position.lat, Position.lon, Position.alt]
                    for i in range(0, len(db_entries), self._insert_batch_size):
                        Position.insert_many(db_entries[i:i+self._insert_batch_size], fields=fields).execute()

                
            self.cleanup_items()

        except ResultTimeout:
            logger.info('Database timeout')

        self._t = Timer(self.sleep_time, self._run)
        self._t.start()

    def update_callsigns(self, position_report):

        # None for a callsign is allowed
        active_callsigns = list(map(lambda m: (m[0], m[4]),  position_report)) # (modeS, callsign)

        for icao_modeS in active_callsigns:        
            
            if icao_modeS[0] not in self.modeS_flight_map:

                # create a new flight even if other flights in db match modes/callsign, but too much time elapsed since last position report
                thresh_timestmp = datetime.datetime.utcnow() - datetime.timedelta(minutes=10)
                flight_results = Flight.select(Flight.id).where(Flight.modeS == icao_modeS[0], Flight.callsign == icao_modeS[1], Flight.last_contact > thresh_timestmp)

                if flight_results and len(flight_results) > 0:
                    flight_id = flight_results[0].id
                    #logger.info('present {:s} ({:s})'.format(icao_modeS[1],icao_modeS[0]))
                else:                    
                    flight_id = Flight.insert(modeS=icao_modeS[0], callsign=icao_modeS[1] ).execute() # TODO: insertMany
                    #logger.info('inserted {:s} ({:s})'.format(icao_modeS[1],icao_modeS[0]))

                self.modeS_flight_map[icao_modeS[0]] = flight_id
            #TODO elif no callsign -> Update

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

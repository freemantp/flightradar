from threading import Timer
from time import sleep
import datetime
import logging

from adsb.modesmixer import ModeSMixer
from adsb.virtualradarserver import VirtualRadarServer
from adsb.military import MilRanges

from adsb.db.dbmodels  import Position
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

        self._mil_ranges = MilRanges(config.data_folder)
        self.interrupted = False
        self._mil_only = config.military_only
        self._db = db
        self.delete_after = config.delete_after
        # see https://stackoverflow.com/questions/35616602/peewee-operationalerror-too-many-sql-variables-on-upsert-of-only-150-rows-8-c#36788489
        self._insert_batch_size = 50

    def is_service_alive(self):
        return self._service.connection_alive

    def cleanup_items(self):

        if self.delete_after > 0:
            threshold_data = datetime.datetime.utcnow() - datetime.timedelta(minutes=self.delete_after)
            query = (Position.delete()
                            .where((Position.timestmp < threshold_data) & (Position.archived == False) ) )

            num_records_deleted = query.execute()
            if num_records_deleted > 0:
                logger.info('Deleting {:d} old records from the datbase'.format(num_records_deleted))


    def _run(self):

        positions = self._service.query_live_positions()

        try:
            if positions:
                # Filter for military icaos
                if self._mil_only:
                    positions = filter(lambda p : self._mil_ranges.is_military(p[0]), positions)

                # Filter out empty positons
                pos_array = list(filter(lambda p : p[1] and p[2], positions))

                if pos_array:
                    #with self._db.atomic():
                    fields = [Position.icao, Position.lat, Position.lon, Position.alt]
                    for i in range(0, len(pos_array), self._insert_batch_size):
                        Position.insert_many(pos_array[i:i+self._insert_batch_size], fields=fields).execute()

            self.cleanup_items()

        except ResultTimeout as e:
            logger.info('Database timeout: {:s}'.format(e))

        self._t = Timer(self.sleep_time, self._run)
        self._t.start()

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

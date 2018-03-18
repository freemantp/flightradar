import threading
import time
import datetime

from adsb.modesmixer import ModeSMixer
from adsb.virtualradarserver import VirtualRadarServer
from adsb.military import MilRanges

from adsb.dbmodels  import Position
from peewee import IntegrityError

class AircaftProcessor(threading.Thread):

    def __init__(self, config, db):

        threading.Thread.__init__(self)

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

    def is_service_alive(self):
        return self._service.connection_alive

    def cleanup_items(self):
        
        threshold_data = datetime.datetime.utcnow() - datetime.timedelta(minutes=self.delete_after)
        query = (Position.delete()
                .where(Position.timestmp <  threshold_data) )
        num_records_deleted = query.execute()
        if num_records_deleted > 0:
            print('Deleting {:d} old records from the datbase'.format(num_records_deleted))

    def run(self):

        while not self.interrupted:

            positions = self._service.query_live_positions()

            if positions:

                # Filter for military icaos
                if self._mil_only:
                    positions = filter(lambda p : self._mil_ranges.is_military(p[0]), positions)

                # Filter out empty positons
                pos_array = list(filter(lambda p : p[1] and p[2], positions))

                if pos_array:
                    with self._db.atomic():
                        fields = [Position.icao, Position.lat, Position.lon, Position.alt]
                        Position.insert_many(pos_array, fields=fields).execute()
                                
            self.cleanup_items()
            time.sleep(1)
            

        print("interupted")

    def __getattr__(self, name):
        return getattr(self.instance, name)

    def get_silhouete_params(self):
        return self._service.get_silhouete_params()

import threading
import time

from adsb.modesmixer import ModeSMixer
from adsb.virtualradarserver import VirtualRadarServer
from adsb.military import MilRanges

class AircraftEntry:

    def __init__(self):
        self.first_seen = time.time()
        self.last_seen = self.first_seen
        self.pos = []
        self._service = None

class AircaftProcessor(threading.Thread):

    def __init__(self, config):

        threading.Thread.__init__(self)

        if config.type == 'mm2':
            self._service = ModeSMixer(config.service_host_name, config.service_port)
        elif config.type == 'vrs':
            self._service = VirtualRadarServer(config.service_host_name, config.service_port)
        else:
            raise ValueError('Service type not specified in config')

        self._mil_ranges = MilRanges(config.data_folder)
        self.interrupted = False
        self._entries = dict()
        self._mil_only = config.military_only

    def get_active_icaos(self):
        return self._entries.keys()

    def get_active_entries(self):
        return self._entries.items()

    def get_entry(self, icao24):
        return self._entries[icao24] if icao24 in self._entries else None

    def is_service_alive(self):
        return self._service.connection_alive

    def cleanup_items(self):

        now = time.time()
        to_delete = []

        for item in self._entries.items():
            delta = int(now - item[1].last_seen)
            if delta > 86400: #24h
                to_delete.append(item[0])

        for icao24 in to_delete:
            self._entries.pop(icao24)
            print("cleaned %s" % icao24)

    def update_data(self, icao24, position=None):

        if icao24 not in self._entries:
            self._entries[icao24] = AircraftEntry()

        timestamp = time.time()

        if position:
            if not self._entries[icao24].pos or self._entries[icao24].pos[-1] != position:
                self._entries[icao24].pos.append(position)
                self._entries[icao24].last_seen = self._entries[icao24].first_seen
        else:
            self._entries[icao24].last_seen = timestamp

    def run(self):

        while not self.interrupted:

            positions = self._service.query_live_positions()

            if positions:
                for entry in positions:
                    icao24 = entry[0]
                    if not self._mil_only or (self._mil_only and self._mil_ranges.is_military(icao24)):
                        if entry[1][0] and entry[1][1]:
                            self.update_data(icao24, entry[1])

            time.sleep(1)
            self.cleanup_items()

        print("interupted")

    def __getattr__(self, name):
        return getattr(self.instance, name)

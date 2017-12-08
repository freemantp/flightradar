import threading
import time

from adsb.modesmixer import ModeSMixer
from adsb.military import MilRanges

class AircraftEntry:

    def __init__(self):
        self.first_seen = time.time()
        self.last_seen = self.first_seen
        self.pos = []


class UpdaterThread(threading.Thread):

    def __init__(self, config):

        threading.Thread.__init__(self)

        self._mm2 = ModeSMixer(config.host, config.port)
        self._mil_ranges = MilRanges(config.data_folder)
        self.interrupted = False
        self._entries = dict()

    def get_active_icaos(self):
        return self._entries.keys()

    def get_active_entries(self):
        return self._entries.items()

    def get_entry(self, icao24):
        return self._entries[icao24] if icao24 in self._entries else None

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
            self._entries[icao24].last_seen = timestamp
            self._entries[icao24].pos.append(position)
        else:
            self._entries[icao24].last_seen = timestamp

    def run(self):

        while not self.interrupted:

            positions = self._mm2.query_live_positions()

            for entry in positions:
                icao24 = entry[0]

                if self._mil_ranges.is_military(icao24):
                    if entry[1][0] and entry[1][1]:
                        self.update_data(icao24, entry[1])

            time.sleep(2)
            self.cleanup_items()

        print("interupted")

    def __getattr__(self, name):
        return getattr(self.instance, name)

import threading
import time

from adsb.modesmixer import ModeSMixer
from adsb.military import MilRanges

class UpdaterThread(threading.Thread):

    def __init__(self, config):

        threading.Thread.__init__(self)
        self.mm2 = ModeSMixer(config.host, config.port)
        self.mil_ranges = MilRanges(config.data_folder)
        self.interrupted = False

        self.aircraft = dict()

    def run(self):

        while not self.interrupted:

            icaos = self.mm2.query_live_aircraft()

            for icao24 in icaos:

                if icao24 not in self.aircraft and self.mil_ranges.is_military(icao24):
                    self.aircraft[icao24] = time.time()


            #print("Processed %d codes" % len(icaos))        
            time.sleep(5)

        print("interupted")

    def __getattr__(self, name):
        return getattr(self.instance, name)
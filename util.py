import time
import signal
import sys

from adsb.config import Config
from adsb.db_updater import DbUpdater
from adsb.modesmixer import ModeSMixer

def signal_handler(signal, frame):
        print('You pressed Ctrl+C!')
        sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)


config = Config()
config.from_file('config.json')

ms = ModeSMixer(config.service_host_name,config.service_port)
print(ms.query_live_positions())

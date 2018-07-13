from adsb.flightradar24 import Flightradar24
from adsb.bazllfr import BazlLFR
from adsb.modesmixer import ModeSMixer
from adsb.virtualradarserver import VirtualRadarServer
from adsb.basestationdb import BaseStationDB
from adsb.tabular import Tabular
from adsb.config import Config

import time
import signal
import sys
import json
import logging

logging.basicConfig(level=logging.INFO)

logger =  logging.getLogger("Updater")

adsb_config = Config()
adsb_config.from_file('config.json')

bs_db = BaseStationDB(adsb_config.data_folder + "BaseStation.sqb")

modes_queried = set()
not_found = set()

update_count = 0
insert_count = 0

def signal_handler(signal, frame):
        logger.info('You pressed Ctrl+C!')
        logger.info('updated: %d, inserted: %d ' % (update_count,insert_count) )

        if not_found:
            logger.info('not found: ')
            for hex in not_found:
                logger.info("\t" + hex)

        sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

def is_swiss(icaohex):
    if icaohex and icaohex[0:2] == "4B":
        third = int(icaohex[2],16)
        if third >=0 and third <=8:
            return True
    return False

def query_modes(hex):

    fr24 = Flightradar24()
    bazl_lfr = BazlLFR()

    if is_swiss(hex):                            
        logger.info("quering Bazl LFR for %s" % hex)
        return bazl_lfr.query_aircraft(hex)
    else:
        logger.info("quering fr24 for %s" % hex)
        return fr24.query_aircraft(hex)

def update_live():

    if adsb_config.type == 'mm2':
        msm = ModeSMixer(adsb_config.service_url)
    else:
         raise ValueError('Service type {:s} is not supported'.format(adsb_config.type))

    while True:
        live_aircraft = msm.query_live_icao24()
        #logger.info("got %d live ones" % len(live_aircraft))

        if live_aircraft:
            for hex in live_aircraft:

                aircraft = bs_db.query_aircraft(hex)

                if aircraft and not aircraft.is_complete():

                    if hex not in modes_queried:

                        aircraft_response = query_modes(hex)

                        modes_queried.add(hex)                        
                        if aircraft_response:
                            logger.info("fr24: %s" % aircraft_response)                            
                            aircraft.merge(aircraft_response)
                            updated = bs_db.update_aircraft(aircraft)
                            global update_count
                            update_count += 1
                            logger.info("%s  - updated=%s" % (aircraft,updated))
                        else:
                            not_found.add(hex)

                if not aircraft:
                    aircraft_response = query_modes(hex)

                    modes_queried.add(hex)
                    if aircraft_response:
                        inserted = bs_db.insert_aircraft(aircraft_response)
                        global insert_count
                        insert_count += 1
                        logger.info("%s  - inserted=%s" % (aircraft_response, inserted))

        #logger.info("sleeping")
        time.sleep(20)

def read_csv():
    for plane in Tabular.parse_csv(adsb_config.data_folder + r'\\Mil.csv'):
        aircraft = bs_db.query_aircraft(plane.modes_hex)
        if aircraft:
            if not aircraft.is_complete():
                bs_db.update_aircraft(plane)
                logger.info("%s updated" % plane.reg)
            else:
                logger.info(plane)
                logger.info(aircraft)
                logger.info("\n")
        else:
            bs_db.insert_aircraft(plane)
            logger.info("%s inserted" % plane.reg)

if __name__ == '__main__':
    logger.info("Starting update")
    update_live()

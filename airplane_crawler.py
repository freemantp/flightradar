from app.adsb.datasource.flightradar24 import Flightradar24
from app.adsb.datasource.bazllfr import BazlLFR
from app.adsb.datasource.adsb_nl import AdsbNL
from app.adsb.datasource.openskynet import OpenskyNet
from app.adsb.datasource.militarymodes_eu import MilitaryModeS
from app.adsb.datasource.secret_base import SecretBasesUk
from app.adsb.datasource.modesmixer import ModeSMixer
from app.adsb.datasource.virtualradarserver import VirtualRadarServer
from app.adsb.db.basestationdb import BaseStationDB
from app.adsb.util.tabular import Tabular
from app.config import Config
from app.adsb.util.logging import init_logging

import time
import signal
import sys
import json
import logging
from os import path

adsb_config = Config()

init_logging(adsb_config.LOGGING_CONFIG)
logger =  logging.getLogger("Updater")

db_file = path.join(adsb_config.DATA_FOLDER, 'BaseStation.sqb')
bs_db = None

if path.exists(db_file):
    bs_db = BaseStationDB(db_file)
else:
    logger.error('database file not found: {:s}'.format(db_file))

sources = [BazlLFR(), 
OpenskyNet(), 
AdsbNL(adsb_config.DATA_FOLDER),
SecretBasesUk(adsb_config.DATA_FOLDER),
Flightradar24(),
MilitaryModeS(adsb_config.DATA_FOLDER)]

modeS_queried = set()
not_found = set()

update_count = 0
insert_count = 0

def signal_handler(signal, frame):
        logger.info('You pressed Ctrl+C!')
        logger.info('updated: %d, inserted: %d ' % (update_count,insert_count) )

        if not_found:
            logger.info('not found: ')
            for modeS in not_found:
                logger.info("\t" + modeS)

        sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

def query_modes(modeS_address):

    aircraft = None

    for s in sources:
        if s.accept(modeS_address):
            aircraft = s.query_aircraft(modeS_address)
            logger.info('[ {:s} ] -> {:s} ({:s})'.format(s.name(), modeS_address, ("success" if aircraft else "failed") ))
            if aircraft:
                return aircraft

    return None

def update_live():

    if adsb_config.RADAR_SERVICE_TYPE == 'mm2':
        msm = ModeSMixer(adsb_config.RADAR_SERVICE_URL)
    else:
         raise ValueError('Service type {:s} is not supported'.format(adsb_config.RADAR_SERVICE_TYPE)) #TODO enable VRS

    while True:
        live_aircraft = msm.query_live_icao24()

        if live_aircraft:
            for modeS in live_aircraft:

                if modeS not in modeS_queried and modeS not in not_found:

                    try:
                        aircraft_db = bs_db.query_aircraft(modeS)
                        if aircraft_db and not aircraft_db.is_complete():

                            aircraft_response = query_modes(modeS)
                            modeS_queried.add(modeS)

                            if aircraft_response:
                                aircraft_db.merge(aircraft_response)
                                if bs_db.update_aircraft(aircraft_db):
                                    global update_count
                                    update_count += 1
                                    logger.info('[ Update ] {:s}'.format(str(aircraft_db)))
                            else:
                                not_found.add(modeS)

                        elif not aircraft_db:

                            aircraft_response = query_modes(modeS)
                            modeS_queried.add(modeS)

                            if aircraft_response:
                                if bs_db.insert_aircraft(aircraft_response):
                                    global insert_count
                                    insert_count += 1
                                    logger.info('[ Inserted ] {:s}'.format(str(aircraft_response)))
                    except:
                        logger.exception("An error occured")

        time.sleep(20)

def read_csv(file):
    for plane in Tabular.parse_csv(adsb_config.DATA_FOLDER + file):
        aircraft = bs_db.query_aircraft(plane.modes_hex)
        if aircraft:
            if not aircraft.is_complete() and not aircraft.is_empty():
                bs_db.update_aircraft(plane)
                logger.info('Updated: {:s}'.format(str(plane)))
        else:            
            bs_db.insert_aircraft(plane)
            logger.info('Inserted: {:s}'.format(str(plane)))

if __name__ == '__main__':

    if len(sys.argv) == 1:
        logger.info("Starting live update")        
        if bs_db:
            update_live()
        else:
            sys.exit(-1)
    elif len(sys.argv) == 2 and sys.argv[1] == '--csv':
        read_csv(r'data.csv')
    else:
        print("Usage: {:s} [--csv]".format(sys.argv[0]))

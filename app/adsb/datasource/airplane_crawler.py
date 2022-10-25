from .flightradar24 import Flightradar24
from .bazllfr import BazlLFR
from .adsb_nl import AdsbNL
from .openskynet import OpenskyNet
from .militarymodes_eu import MilitaryModeS
from .secret_base import SecretBasesUk
from .modesmixer import ModeSMixer
from ..db.basestationdb import BaseStationDB
from ..util.tabular import Tabular
from ..util.logging import init_logging

import logging
from os import path

logger =  logging.getLogger("Crawler")

class AirplaneCrawler:

    sources = []
    modeS_queried = set()
    not_found = set()
    update_count = 0
    insert_count = 0
    bs_db = None
    msm = None

    def __init__(self, config):

        init_logging(config.LOGGING_CONFIG)

        db_file = path.join(config.DATA_FOLDER, 'BaseStation.sqb')

        if path.exists(db_file):
            self.bs_db = BaseStationDB(db_file)
        else:
            logger.error('database file not found: {:s}'.format(db_file))

        assert self.bs_db

        #TODO: use app.modes_util instead of instantiating it for each source

        self.sources = [BazlLFR(), 
            OpenskyNet(), 
            AdsbNL(config.DATA_FOLDER),
            SecretBasesUk(config.DATA_FOLDER),
            Flightradar24(),
            MilitaryModeS(config.DATA_FOLDER)]

        if config.RADAR_SERVICE_TYPE == 'mm2':
            self.msm = ModeSMixer(config.RADAR_SERVICE_URL)
        else:
            raise ValueError('Service type {:s} is not supported'.format(self.config.RADAR_SERVICE_TYPE)) #TODO enable VRS

    def query_modes(self, modeS_address):

        aircraft = None

        logger.info("query_modes")

        for s in self.sources:
            if s.accept(modeS_address):
                aircraft = s.query_aircraft(modeS_address)
                logger.info('[{:s}] -> {:s} ({:s})'.format(s.name(), modeS_address, ("success" if aircraft else "failed") ))
                if aircraft:
                    return aircraft

        return None

    def crawl_sources(self):

        live_aircraft = self.msm.query_live_icao24()

        if live_aircraft:
            for modeS in live_aircraft:

                if modeS not in self.modeS_queried and modeS not in self.not_found:

                    try:
                        aircraft_db = self.bs_db.query_aircraft(modeS)
                        if aircraft_db and not aircraft_db.is_complete():

                            aircraft_response = self.query_modes(modeS)
                            self.modeS_queried.add(modeS)

                            if aircraft_response:
                                aircraft_db.merge(aircraft_response)
                                if self.bs_db.update_aircraft(aircraft_db):
                                    self.update_count += 1
                                    logger.info('Updated {:s}'.format(str(aircraft_db)))
                            else:
                                self.not_found.add(modeS)

                        elif not aircraft_db:

                            aircraft_response = self.query_modes(modeS)
                            self.modeS_queried.add(modeS)

                            if aircraft_response:
                                if self.bs_db.insert_aircraft(aircraft_response):
                                    self.insert_count += 1
                                    logger.info('Inserted {:s}'.format(str(aircraft_response)))
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except:
                        logger.exception("An error occured")

def read_csv(file):
    for plane in Tabular.parse_csv(adsb_config.DATA_FOLDER + file):
        aircraft = self.bs_db.query_aircraft(plane.modes_hex)
        if aircraft:
            if not aircraft.is_complete() and not aircraft.is_empty():
                self.bs_db.update_aircraft(plane)
                logger.info('Updated: {:s}'.format(str(plane)))
        else:            
            self.bs_db.insert_aircraft(plane)
            logger.info('Inserted: {:s}'.format(str(plane)))
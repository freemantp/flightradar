import requests
from requests.exceptions import HTTPError
import logging
from typing import Optional
from ....core.models.aircraft import Aircraft
from . import AircraftMetadataSource

logger = logging.getLogger('OpenSky')


class OpenskyNet(AircraftMetadataSource):

    """ Opensky-Network """

    def __init__(self) -> None:

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_6; en-en) AppleWebKit/533.19.4 (KHTML, like Gecko) Version/5.0.3 Safari/533.19.4',
            "Content-type": "application/json",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de,en-US;q=0.7,en;q=0.3"
        }
        self.timeout = 5.0
        self.maxretires = 5

    @staticmethod
    def name() -> str:
        return 'Opensky'

    def accept(self, modes_address: str) -> bool:
        return True

    def query_aircraft(self, mode_s_hex: str) -> Optional[Aircraft]:
        """ queries aircraft data """

        try:
            
            url = 'https://opensky-network.org/api/metadata/aircraft/icao/{:s}'.format(mode_s_hex)
            response = requests.get(url, headers=self.headers, timeout=self.timeout)

            if response.status_code == requests.codes.not_found:
                return None

            response.raise_for_status()

            aircraft = response.json()

            if aircraft:
                modeS = aircraft['icao24'].upper()
                reg = aircraft['registration']
                icao_type_code = aircraft['typecode']
                op = aircraft['operator']

                aircraft_type_description = (aircraft['model'] 
                            if aircraft['model'].startswith(aircraft['manufacturerName']) 
                            else  '{:s} {:s}'.format(aircraft['manufacturerName'], aircraft['model']) )

                if modeS and reg and icao_type_code and aircraft['model']:
                    return Aircraft(modeS, reg=reg, icao_type_code=icao_type_code, aircraft_type_description=aircraft_type_description, operator=op, source=self.name())

        except HTTPError as http_err:
            logger.exception(http_err)
        except (KeyboardInterrupt, SystemExit):
            raise            
        except:
            logger.exception('An unexpected error occured')


        return None
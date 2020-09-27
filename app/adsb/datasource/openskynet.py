import requests
from requests.exceptions import HTTPError
import time
import logging
import ssl

from ..aircraft import Aircraft
from ..util.modes_util import ModesUtil

logger = logging.getLogger('OpenSky')


class OpenskyNet:

    """ Opensky-Network """

    def __init__(self):

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_6; en-en) AppleWebKit/533.19.4 (KHTML, like Gecko) Version/5.0.3 Safari/533.19.4',
            "Content-type": "application/json",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de,en-US;q=0.7,en;q=0.3"
        }
        self.timeout = 5.0
        self.maxretires = 5

    @staticmethod
    def name():
        return 'Opensky'

    def accept(self, modes_address):
        return True

    def query_aircraft(self, mode_s_hex):
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
                type1 = aircraft['typecode']
                op = aircraft['operator']

                type2 = (aircraft['model'] 
                            if aircraft['model'].startswith(aircraft['manufacturerName']) 
                            else  '{:s} {:s}'.format(aircraft['manufacturerName'], aircraft['model']) )

                if modeS and reg and type1 and aircraft['model']:
                    return Aircraft(modeS, reg, type1, type2, op)

        except HTTPError as http_err:
            logger.exception(http_err)
        except (KeyboardInterrupt, SystemExit):
            raise            
        except:
            logger.exception('An unexpected error occured')


        return None
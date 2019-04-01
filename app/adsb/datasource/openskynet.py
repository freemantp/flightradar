from http.client import HTTPSConnection, RemoteDisconnected, IncompleteRead
from socket import error as SocketError
import json
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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:61.0) Gecko/20100101 Firefox/61.0',
            "Content-type": "application/json",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de,en-US;q=0.7,en;q=0.3"
        }
        self.timeout = 10
        self.maxretires = 5

    @staticmethod
    def name():
        return 'Opensky'

    def accept(self, modes_address):
        return True

    def query_aircraft(self, mode_s_hex):
        """ queries aircraft data """

        try:
            
            conn = HTTPSConnection("opensky-network.org")
            conn.request('GET', '/api/metadata/aircraft/icao/{:s}'.format(mode_s_hex), headers=self.headers)

            res = conn.getresponse()
            if res.status == 200:

                aircraft = json.loads(res.read().decode())

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
            elif res.status == 404:                    
                return None
            else:
                res.read()
                logger.error('Unexpected http code {:d}'.format(res.status))
        except RemoteDisconnected:
            logger.exception("RemoteDisconnected")
        except IncompleteRead:
            logger.exception("IncompleteRead")
        except SocketError :
            logger.exception("SocketError")


        return None
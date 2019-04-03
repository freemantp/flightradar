from http.client import HTTPSConnection, RemoteDisconnected, IncompleteRead
from socket import error as SocketError
import json
import time
import logging
import ssl

from bs4 import BeautifulSoup

from ..aircraft import Aircraft
from ..util.modes_util import ModesUtil

logger = logging.getLogger('MilModeS.eu')


class MilitaryModeS:   

    """ Live Military Mode S """

    def __init__(self, config_folder):

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:61.0) Gecko/20100101 Firefox/61.0',
            "Content-type": "application/json",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de,en-US;q=0.7,en;q=0.3"
        }
        self.timeout = 10
        self.maxretires = 5
        self.modes_util = ModesUtil(config_folder)

    @staticmethod
    def name():
        return 'Live Military Mode S'

    def accept(self, modes_address):
        return self.modes_util.is_military(modes_address)

    def query_aircraft(self, mode_s_hex):
        """ queries aircraft data """

        try:
            
            conn = HTTPSConnection("www.live-military-mode-s.eu")
            conn.request('GET', '/military mode-s database/search/searchMilHex.php?Code={:s}&submit4=Search'.format(mode_s_hex), headers=self.headers)

            res = conn.getresponse()
            if res.status == 200:

                data = res.read().decode()
                soup = BeautifulSoup(data, 'html.parser')

                aircraft = Aircraft(mode_s_hex)

                index = 0
                for td in soup.table.find_all('td', width='40%'):

                    if index == 0:
                        aircraft.reg = td.text
                    elif index == 2:
                        aircraft.type2 = td.text
                    elif index == 4:
                        aircraft.operator = td.text

                    index = index + 1

                return aircraft

            elif res.status == 404:                    
                return None
            else:
                res.read()
                logger.error('Unexpected http code {:d}'.format(res.status))
        except (RemoteDisconnected, IncompleteRead, SocketError) as ex:
            logger.exception(ex)
        except:
            logger.exception('An unexpected error occured')

        return None
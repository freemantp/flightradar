import time
import logging
import ssl
import requests
from requests.exceptions import HTTPError

from bs4 import BeautifulSoup

from ..aircraft import Aircraft
from ..util.modes_util import ModesUtil

logger = logging.getLogger('MilModeS.eu')


class MilitaryModeS:   

    """ Live Military Mode S """

    def __init__(self, config_folder):

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_6; en-en) AppleWebKit/533.19.4 (KHTML, like Gecko) Version/5.0.3 Safari/533.19.4',
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

    def sanitize_known_issues(self, aircraft):

        if aircraft:

            if not aircraft.type1:
                # Sanitize eurofighters
                if  aircraft.type2 == 'EF-2000':
                    aircraft.type1= 'EUFI'
                    aircraft.type2 = 'Eurofighter EF-2000 Typhoon'
            # Prevent empty type codes
            elif aircraft.type1.strip() == 'None' or aircraft.type1.strip() == '-':
                aircraft.type1 == None
            
            # Sanitize registrations
            if aircraft.reg:
                if (len(aircraft.reg) == 4 and ((aircraft.reg[0].isdigit() and aircraft.reg.count('x') == 3) or aircraft.reg.count('x') == 4)):
                    aircraft.reg = None
                elif aircraft.reg.strip() == '-':
                    aircraft.reg = None
            else:
                aircraft.reg = None

            # Remove empty operators
            if not aircraft.operator or aircraft.operator.strip() == '-':
                aircraft.operator = None


    def query_aircraft(self, mode_s_hex):
        """ queries aircraft data """

        try:

            url = 'https://www.live-military-mode-s.eu/military mode-s database/search/searchMilHex.php?Code={:s}&submit4=Search'.format(mode_s_hex)
            response = requests.get(url, headers=self.headers)            
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            aircraft = Aircraft(mode_s_hex)

            index = 0
            for td in soup.table.find_all('td', width='40%'):

                if index == 0:
                    aircraft.reg = td.text if td.text else None
                elif index == 2:
                    aircraft.type2 = td.text if td.text else None
                elif index == 4:
                    aircraft.operator = td.text if td.text else None

                index = index + 1

            self.sanitize_known_issues(aircraft)
            return aircraft

        except HTTPError as http_err:
            logger.exception(http_err)
        except (KeyboardInterrupt, SystemExit):
            raise            
        except:
            logger.exception('An unexpected error occured')

        return None
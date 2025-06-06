import logging
import requests
from requests.exceptions import HTTPError
from typing import Optional

from bs4 import BeautifulSoup

from ....core.models.aircraft import Aircraft
from ....core.utils.modes_util import ModesUtil
from . import AircraftMetadataSource

logger = logging.getLogger('MilModeS.eu')


class MilitaryModeS(AircraftMetadataSource):   

    """ Live Military Mode S """

    def __init__(self, config_folder: str) -> None:

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_6; en-en) AppleWebKit/533.19.4 (KHTML, like Gecko) Version/5.0.3 Safari/533.19.4',
            "Content-type": "application/json",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de,en-US;q=0.7,en;q=0.3"
        }
        self.timeout = 5.0
        self.maxretires = 5
        self.modes_util = ModesUtil(config_folder)

    @staticmethod
    def name() -> str:
        return 'Live Military Mode S'

    def accept(self, modes_address: str) -> bool:
        return self.modes_util.is_military(modes_address)

    def sanitize_known_issues(self, aircraft: Optional[Aircraft]) -> None:

        if aircraft:

            if not aircraft.icao_type_code:
                # Sanitize eurofighters
                if  aircraft.aircraft_type_description == 'EF-2000':
                    aircraft.icao_type_code = 'EUFI'
                    aircraft.aircraft_type_description = 'Eurofighter EF-2000 Typhoon'
            # Prevent empty type codes
            elif aircraft.icao_type_code.strip() == 'None' or aircraft.icao_type_code.strip() == '-':
                aircraft.icao_type_code == None
            
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


    def query_aircraft(self, mode_s_hex: str) -> Optional[Aircraft]:
        """ queries aircraft data """

        try:

            url = 'https://www.live-military-mode-s.eu/military mode-s database/search/searchMilHex.php?Code={:s}&submit4=Search'.format(mode_s_hex)
            response = requests.get(url, headers=self.headers, timeout=self.timeout)            
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            aircraft = Aircraft(mode_s_hex, source=self.name())

            index = 0
            for td in soup.table.find_all('td', width='40%'):

                if index == 0:
                    aircraft.reg = td.text if td.text else None
                elif index == 2:
                    aircraft.aircraft_type_description = td.text if td.text else None
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
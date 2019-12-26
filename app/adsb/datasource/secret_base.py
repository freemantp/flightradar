import json
import time
import logging
import ssl
import requests
from requests.exceptions import HTTPError

from bs4 import BeautifulSoup

from ..aircraft import Aircraft
from ..util.modes_util import ModesUtil

logger = logging.getLogger('SecretBasesUk')

class SecretBasesUk:

    MODE_S_FIELD = 'Mode S transponder'
    ICAO_TYPE_FIELD = 'ICAO code'
    REGISTRATION_FIELD = 'Registration'
    SERIAL_FIELD = 'Serial No'

    """ Secret Bases UK """

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
        return 'Secret Bases UK'

    def accept(self, modes_address):
        return self.modes_util.is_military(modes_address)

    def is_sane_field(self, field_content):
        return 'Transponder Logs' not in field_content

    def query_aircraft(self, mode_s_hex):
        """ queries aircraft data """

        try:

            url = 'https://www.secret-bases.co.uk/aircraft/{:s}'.format(mode_s_hex)
            response = requests.get(url, headers=self.headers)            
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            aircraft = Aircraft(mode_s_hex)
            raw_line =  str(soup.body.h1).replace('</h1>', '', 1).replace('<h1>', '', 1)

            named_fields = dict()
            unnamed_fields = []

            for field in raw_line.split('<br/>'):
                if ':' in field:
                    elements = field.split(':')
                    value = elements[1].strip()
                    named_fields[elements[0]] = value if value else None
                else:
                    unnamed_fields.append(field.strip())

            if self.ICAO_TYPE_FIELD in named_fields:
                aircraft.type1 = named_fields[self.ICAO_TYPE_FIELD]
            if self.REGISTRATION_FIELD in named_fields:
                aircraft.reg = named_fields[self.REGISTRATION_FIELD]

            if len(unnamed_fields) == 3 and self.is_sane_field(unnamed_fields[1]) and self.is_sane_field(unnamed_fields[2]):
                aircraft.operator = unnamed_fields[1]
                aircraft.type2 = unnamed_fields[2]
            elif len(unnamed_fields) == 2 and self.is_sane_field(unnamed_fields[1]):
                aircraft.type2 = unnamed_fields[1]
            else:
                logger.error('Could not parse Fields')
                return None

            return aircraft

        except HTTPError as http_err:
            logger.exception(http_err)
        except (KeyboardInterrupt, SystemExit):
            raise            
        except:
            logger.exception('An unexpected error occured')

        return None
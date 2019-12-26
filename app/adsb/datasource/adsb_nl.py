import time
import logging
import ssl
import re
import requests
from requests.exceptions import HTTPError
from bs4 import BeautifulSoup

from ..aircraft import Aircraft
from ..util.modes_util import ModesUtil

logger = logging.getLogger('ADSB-NL')

class AdsbNL:

    """ ads-b.nl Queries """

    def __init__(self, config_folder):
        
        self.headers = {
            'User-Agent' : 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_6; en-en) AppleWebKit/533.19.4 (KHTML, like Gecko) Version/5.0.3 Safari/533.19.4',
            "Content-type": "application/json",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de,en-US;q=0.7,en;q=0.3"
        }
        self.timeout = 10
        self.maxretires = 5
        self.modes_util = ModesUtil(config_folder)

    @staticmethod
    def name():
        return 'ads-b.nl'

    def accept(self, modes_address):
        return self.modes_util.is_military(modes_address)

    @staticmethod
    def split_parenthesis(value):

        """ Splits strings in the form 'A ( B )' into a tuple A, B """

        regex = r"(\w+)\s+\(\s+(.*)\s\)"
        m = re.search(regex, value)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        else:
            return None        

    def query_aircraft(self, mode_s_hex):

        """ queries aircraft data """

        try:
            url = 'http://www.ads-b.nl/aircraft.php?id_aircraft={:d}'.format(int(mode_s_hex, 16))

            response = requests.get(url, headers=self.headers)            
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            keys = []
            values = []

            index = 0
            for sib in soup.body.find('div', text='Registration: ').parent:
                if sib.name == 'div':
                    
                    (keys if (index % 2 == 0) else values).append(sib.string.strip())
                    index = index + 1

            if len(keys) == len(values) and len(keys) == 7:

                modeS_tuple = AdsbNL.split_parenthesis(values[3])
                if modeS_tuple:
                    modeS = modeS_tuple[0]
                else:
                    return None

                type_tuple = AdsbNL.split_parenthesis(values[1])
                if type_tuple:
                    icaoType = type_tuple[0]
                    full_type = type_tuple[1]
                else:
                    return None                

                reg = values[0]

                return Aircraft(modeS,reg,icaoType,full_type)

        except HTTPError as http_err:
            logger.exception(http_err)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            logger.exception('An unexpected error occured')    

        return None

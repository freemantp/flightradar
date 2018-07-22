from http.client import HTTPConnection, RemoteDisconnected, IncompleteRead
from socket import error as SocketError
import json
import time
import logging
import ssl
import re
from bs4 import BeautifulSoup

from ..aircraft import Aircraft
from ..util.modes_util import ModesUtil

logger = logging.getLogger('ADSB-NL')


class AdsbNL:

    """ ads-b.nl Queries """

    def __init__(self, config_folder):

        self.conn = HTTPConnection('www.ads-b.nl')
        self.headers = {
            'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:61.0) Gecko/20100101 Firefox/61.0',
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
            
            self.conn.request('GET', '/aircraft.php?id_aircraft={:d}'.format(int(mode_s_hex, 16)), headers=self.headers)
            res = self.conn.getresponse()
            if res.status == 200:

                data = res.read().decode()
                soup = BeautifulSoup(data, 'html.parser')

                keys = []
                values = []

                index = 0
                for sib in soup.body.find('h1', text='Aircraft info').next_siblings:
                    if sib.name == 'div':
                        (keys if (index % 2 == 0) else values).append(sib.string.strip())
                        index = index + 1

                if len(keys) == len(values) and len(keys) == 6:

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
            else:
                res.read()
                raise ValueError('Unexpected http code: %s' % res.status)

        except RemoteDisconnected:
            logger.error("RemoteDisconnected")
        except IncompleteRead:
            logger.error("IncompleteRead")

        return None

import time
import logging
import ssl
import requests
from requests.exceptions import HTTPError

from ..aircraft import Aircraft
from ..util.modes_util import ModesUtil

logger = logging.getLogger('BAZL-LFR')

class BazlLFR:

    """ Bazl LFR Queries """

    def __init__(self):

        self.known_replacements = dict()

        self.known_replacements['C SERIES AIRCRAFT LIMITED PARTNERSHIP'] = 'Bombardier'
        self.known_replacements['REIMS AVIATION S.A.'] = 'Cessna (Reims)'
        self.known_replacements['AIRBUS S.A.S.'] = 'Airbus'
        self.known_replacements['AIRBUS INDUSTRIE'] = 'Airbus'
        self.known_replacements['CESSNA AIRCRAFT COMPANY'] = 'Cessna'
        self.known_replacements['AGUSTAWESTLAND S.P.A.'] = 'Agusta Westland'
        self.known_replacements['THE BOEING COMPANY'] = 'Boeing'
        self.known_replacements['ROBINSON HELICOPTER COMPANY'] = 'Robinson'
        self.known_replacements['PILATUS AIRCRAFT LTD.'] = 'Pilatus'

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
        return 'BAZL LFR'

    def accept(self, modes_address):
        return ModesUtil.is_swiss(modes_address)

    def query_aircraft(self, mode_s_hex):
        """ queries aircraft data """

        try:
            post_body = {
                'current_page_number':	1,
                'language':	'en',
                'page_result_limit':	10,
                'query': {
                    'icao':	mode_s_hex,
                    'showDeregistered':	False
                },
                'queryProperties': {
                    'icao':	mode_s_hex,
                    'showDeregistered':	False},
                'sort_list': 'registration'
            }

            url = 'https://app02.bazl.admin.ch/web/bazl-backend/lfr'.format(mode_s_hex)
            response = requests.post(url, json=post_body, headers=self.headers)            
            response.raise_for_status()

            response_body = response.json()

            if response_body:
                aircraft = response_body[0]
                reg = aircraft['registration']
                type1 = aircraft['icaoCode']

                manufacturer = aircraft['manufacturer'] \
                    if aircraft['manufacturer'] not in self.known_replacements \
                    else self.known_replacements[aircraft['manufacturer']]

                model = aircraft['aircraftModelType']
                marketing_desc = aircraft['details']['marketing']

                for op in aircraft['ownerOperators']:
                    if 'Haupthalter' in op['holderCategory']['categoryNames']['de']:
                        operator = op['ownerOperator']

                # Sanitize strings
                manufacturer = manufacturer.title() if manufacturer.isupper() else manufacturer
                operator = operator.title() if operator.isupper() else operator
                model = model.title() if model.isupper() else model
                marketing_desc = '' if marketing_desc == 'N/A' else marketing_desc
                marketing_desc = marketing_desc.title() if marketing_desc.isupper() else marketing_desc

                type2 = '{:s} {:s}'.format(manufacturer, model)
                type2 = type2 + ' ({:s})'.format(marketing_desc) if marketing_desc else type2

                return Aircraft(mode_s_hex, reg, type1, type2, operator)
                
        except HTTPError as http_err:
            logger.exception(http_err)
        except (KeyboardInterrupt, SystemExit):
            raise            
        except:
            logger.exception('An unexpected error occured')    

        return None
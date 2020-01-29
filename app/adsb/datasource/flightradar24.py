import requests
from requests.exceptions import HTTPError
import time
import logging

from ..aircraft import Aircraft

logger = logging.getLogger('FR24')

class Flightradar24:

    """ Flightradar24 Queries """

    def __init__(self):

        self.headers = {
            'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0',
            "Content-type": "application/json",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de,en-US;q=0.7,en;q=0.3"
        }
        self.maxretires = 5
        self.failcounter = 0

    @staticmethod
    def name():
        return 'FR24'

    def accept(self, modes_address):
        return True

    @staticmethod
    def _get_timeout_sec(retry_attempt):

        """ Seconds in function of retry attempt, basically a Fibonacci seq with offset"""
        n = 6 + retry_attempt
        #
        a,b = 1,1
        for i in range(n-1):
            a,b = b,a+b

        return a

    def _fail_and_sleep(self):
        seconds = Flightradar24._get_timeout_sec(self.failcounter)
        logger.warn('Sleeping for {:d}sec'.format(seconds))
        time.sleep(seconds)
        self.failcounter += 1

    def query_aircraft(self, mode_s_hex):

        """ queries aircraft data """

        self.failcounter = 0
        while self.failcounter < self.maxretires:
            try:

                url = 'https://api.flightradar24.com/common/v1/search.json?fetchBy=reg&query={:s}'.format(mode_s_hex)
                response = requests.get(url, headers=self.headers)            



                if response.status_code == requests.codes.ok:
                    json_obj = response.json()
                    if json_obj['result']['response']['aircraft']['data']:
                        aircraft = json_obj['result']['response']['aircraft']['data'][0]
                        reg = aircraft['registration']
                        type1 = aircraft['model']['code']
                        type2 = aircraft['model']['text']
                        if aircraft['airline']:
                            operator = aircraft['airline']['name']
                        else:
                            operator = None
                        return Aircraft(mode_s_hex, reg, type1, type2, operator)

                elif response.status_code == requests.codes.payment:                    
                    logger.warn('HTTP 402 - Payment Required')
                    self._fail_and_sleep()
                elif response.status_code >= 500 and response.status_code < 600:
                     self._fail_and_sleep()              
                else:
                    logger.warn('Unexpected http code: {}'.format(response.status_code))

            except HTTPError as http_err:

                if http_err.response.status_code_code == requests.codes.payment:
                    logger.warn('HTTP 402 - Payment Required')            
                else:
                    logger.exception(http_err)
                self._fail_and_sleep()
            except (KeyboardInterrupt, SystemExit):
                raise                
            except:
                logger.exception('An unexpected error occured')
                self._fail_and_sleep() 

        if self.failcounter == self.maxretires:
            logger.warning('Too many failures for {:s}, giving up'.format(mode_s_hex))
        
        return None



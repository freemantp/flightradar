from http.client import HTTPSConnection, RemoteDisconnected, IncompleteRead
import json
import time

from .aircraft import Aircraft

class Flightradar24:

    """ Flightradar24 Queries """

    def __init__(self):

        self.conn = HTTPSConnection("api.flightradar24.com")
        self.headers = { 
            'User-Agent' : 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:57.0) Gecko/20100101 Firefox/57.0',
            "Content-type": "application/json", 
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de,en-US;q=0.7,en;q=0.3"
        }
        self.timeout = 10
        self.maxretires = 5

    def query_aircraft(self, mode_s_hex):

        """ queries aircraft data """

        failcounter = 0

        while failcounter < self.maxretires:
            try:
                self.conn.request('GET', "/common/v1/search.json?fetchBy=reg&query=%s" % mode_s_hex, headers=self.headers)
                res = self.conn.getresponse()
                if res.status == 200:

                    json_obj = json.loads(res.read().decode())

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

                elif res.status == 402:
                    failcounter += 1
                    res.read()

                    print('402, sleeping for {}sec'.format( self.timeout ) )
                    time.sleep( self.timeout)
                    self.timeout += 1
                else:
                    res.read()
                    raise ValueError('Unexpected http code: %s' % res.status)
            except RemoteDisconnected:
                failcounter += 1
                time.sleep(failcounter * 5)
                print("error, waiting some time")
            except IncompleteRead:
                failcounter += 1
                time.sleep(failcounter * 3)
                print("error, waiting some time")

        return None

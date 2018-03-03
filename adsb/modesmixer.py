from http.client import HTTPConnection, HTTPSConnection
from base64 import b64encode
from urllib.parse import urlparse

import json


class ModeSMixer:

    """ ModeSMixer Queries """

    def __init__(self, url):

        self._url_parms = urlparse(url)

        if self._url_parms.scheme == 'http':
            self.conn = HTTPConnection(self._url_parms.netloc)
        elif self._url_parms.scheme == 'https':
            self.conn = HTTPSConnection(self._url_parms.netloc)
        else:
            raise ValueError('Invalid protocol in service url')

        self.body = """{"req":"getStats","data":{"statsType":"flights","id":%s}}"""
        self.headers = {
            "Content-type": "application/json", "Accept": "*/*"
        }

        self.connection_alive = True
        self.epoch = 0

    def __del__(self):
        self.conn.close()

    def get_flight_info(self, force_initial=False):

        try:
            msg_body = self.body % (0 if force_initial else self.epoch)

            self.conn.request('POST', self._url_parms.path +
                              '/json', body=msg_body, headers=self.headers)
            res = self.conn.getresponse()
            data = res.read()

            json_obj = json.loads(data.decode())

            flights = json_obj['stats']['flights']
            self.epoch = json_obj['stats']['epoch']
            self.connection_alive = True
            return flights

        except ConnectionRefusedError as cre:
            print(cre)
        except OSError as e:
            print(e)

        self.connection_alive = False
        return None

    def query_live_icao24(self):

        flight_data = self.get_flight_info()

        if flight_data:
            hexcodes = []
            for fl in flight_data:
                if fl:
                    icaohex = str(fl['I'])
                    hexcodes.append(icaohex)
            return hexcodes
        else:
            return None

    def query_live_positions(self):
        """ Returns a list of Mode-S adresses with current position information"""

        flight_data = self.get_flight_info()

        if flight_data:
            flights = []
            for flight in flight_data:
                if 'LA' in flight and 'LO' in flight and 'A' in flight:

                    icao24 = str(flight['I'])
                    lat = flight['LA'] if 'LA' in flight and flight['LA'] else None
                    lon = flight['LO'] if 'LO' in flight and flight['LO'] else None
                    alt = flight['A'] if 'A' in flight and flight['A'] else None

                    if lat and lon or alt:
                        flights.append((icao24, (lat, lon, alt)))
            return flights
        else:
            return None

    def get_silhouete_params(self):
        return {
            'prefix': "{:s}/img/silhouettes/".format(self._url_parms.geturl()),
            'suffix': ".bmp"
        }

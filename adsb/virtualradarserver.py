from http.client import HTTPConnection, HTTPSConnection
from base64 import b64encode
from urllib.parse import urlparse

import json


class VirtualRadarServer:

    """ VirtualRadarServer Queries """

    def __init__(self, url):

        self._url_parms = urlparse(url)

        if self._url_parms.scheme == 'http':
            self.conn = HTTPConnection(self._url_parms.netloc)
        elif self._url_parms.scheme == 'https':
            self.conn = HTTPSConnection(self._url_parms.netloc)
        else:
            raise ValueError('Invalid protocol in service url')

        self.headers = {
            "Accept": "application/json"
        }

        self.connection_alive = True

    def __del__(self):
        self.conn.close()

    def query_live_positions(self):
        """ Returns a list of Mode-S adresses with current position information"""

        try:

            self.conn.request('POST', self._url_parms.path +
                              '/AircraftList.json', headers=self.headers)
            res = self.conn.getresponse()
            data = res.read()

            if data:
                json_data = json.loads(data.decode())

                flights = []

                for acjsn in json_data['acList']:

                    icao24 = str(acjsn['Icao'])
                    lat = acjsn['Lat'] if 'Lat' in acjsn and acjsn['Lat'] else None
                    lon = acjsn['Long'] if 'Long' in acjsn and acjsn['Long'] else None
                    alt = acjsn['Alt'] if 'Alt' in acjsn and acjsn['Alt'] else None

                    if lat and lon or alt:
                        flights.append((icao24, (lat, lon, alt)))

                self.connection_alive = True
                return flights

            else:
                print("Request to {:s} failed".format(
                    self._url_parms.geturl()))

        except ConnectionRefusedError as cre:
            print(cre)
        except OSError as e:
            print(e)
        self.connection_alive = False
        return None

    def get_silhouete_params(self):
        return {
            'prefix': "{:s}/images/File-|".format(self._url_parms.geturl()),
            'suffix': "/Type.png"
        }

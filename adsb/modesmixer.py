from http.client import HTTPConnection
import json
from base64 import b64encode

from .aircraft import Aircraft

class ModeSMixer:

    """ ModeSMixer Queries """

    def __init__(self, host, port):

        self.host = host
        self.port = port
        self.epoch = 0

        self.headers = { 
            'Authorization' : 'Basic %s' %  b64encode(b"user:pwdhere").decode("ascii"),
            "Content-type": "application/json", "Accept": "*/*"
        }

        self.body = """{"req":"getStats","data":{"statsType":"flights","id":%s}}"""

    def get_flight_info(self, force_initial=False):
        msg_body = self.body % (0 if force_initial else self.epoch)

        conn = HTTPConnection(self.host, self.port)
        conn.request('POST', '/json', body=msg_body, headers=self.headers)
        res = conn.getresponse()
        data = res.read()  

        json_obj = json.loads(data.decode())

        flights = json_obj['stats']['flights']
        self.epoch = json_obj['stats']['epoch']
        
        conn.close()
        return flights

    def query_live_icao24(self):

        hexcodes = []

        for fl in self.get_flight_info():
            icaohex = str(fl['I'])
            hexcodes.append(icaohex)

        
        return hexcodes

    def query_live_positions(self):

        """ Returns a list of Mode-S adresses with current position information"""

        flights = []

        for flight in self.get_flight_info():
            if 'LA' in flight and 'LO' in flight and 'A' in flight:

                icao24 = str(flight['I'])
                lat = flight['LA'] if 'LA' in flight and flight['LA'] else None
                lon = flight['LO'] if 'LO' in flight and flight['LO'] else None
                alt = flight['A'] if 'A' in flight and flight['A'] else None

                if lat and lon or alt:
                    flights.append((icao24, (lat, lon, alt)))

        return flights
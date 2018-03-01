from http.client import HTTPConnection
from base64 import b64encode
import json

class VirtualRadarServer:

    """ VirtualRadarServer Queries """

    def __init__(self, host, port):

        self.service_host_name = host
        self.service_port = port

    def query_live_positions(self):

        """ Returns a list of Mode-S adresses with current position information"""

        try:

            conn = HTTPConnection(self.service_host_name, self.service_port)
            conn.request('GET', '/VirtualRadar/AircraftList.json')
            res = conn.getresponse()
            data = res.read()
            json_data = json.loads(data.decode())

            flights = []

            for acjsn in json_data['acList']:

                icao24 = str(acjsn['Icao'])
                lat = acjsn['Lat'] if 'Lat' in acjsn and acjsn['Lat'] else None
                lon = acjsn['Long'] if 'Long' in acjsn and acjsn['Long'] else None
                alt = acjsn['Alt'] if 'Alt' in acjsn and acjsn['Alt'] else None

                if lat and lon or alt:
                    flights.append((icao24, (lat, lon, alt)))

            return flights
        
        except ConnectionRefusedError as cre:
            print(cre)
        except OSError as e:
            print(e)
        
        return None

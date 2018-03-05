from adsb.radarservice import RadarService
import json

class VirtualRadarServer(RadarService):

    """ VirtualRadarServer Queries """

    def __init__(self, url):
        RadarService.__init__(self, url) 

    def query_live_positions(self):
        """ Returns a list of Mode-S adresses with current position information"""

        conn = self.get_connection()

        try:
            conn.request('POST', self._url_parms.path +
                              '/AircraftList.json', headers=self.headers)
            res = conn.getresponse()
            data = res.read()

            if res.code == 200:
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
            else:
                print("[VRS] unexpected HTTP response: {:d}".format(res.code))

        except ConnectionRefusedError as cre:
            print(cre)
        except OSError as e:
            print(e)

        if conn:
            conn.close()    
        self.connection_alive = False
        return None

    def get_silhouete_params(self):
        return {
            'prefix': "{:s}/images/File-|".format(self._url_parms.geturl()),
            'suffix': "/Type.png"
        }

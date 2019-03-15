from adsb.datasource.radarservice import RadarService
import json
import logging

logger = logging.getLogger(__name__)

class ModeSMixer(RadarService):

    """ ModeSMixer Queries """

    def __init__(self, url):

        RadarService.__init__(self, url)

        self.headers['Content-type'] = 'application/json'
        self.body = """{"req":"getStats","data":{"statsType":"flights","id":%s}}"""
        self.epoch = 0

    def get_request_body(self):
        return self.body % self.epoch

    def get_flight_info(self, force_initial=False):

        conn = self.get_connection()

        try:
            msg_body = self.body % (0 if force_initial else self.epoch)

            conn.request('POST', self._url_parms.path +
                         '/json', body=msg_body, headers=self.headers)
            res = conn.getresponse()
            data = res.read()

            if res.code == 200:
                json_obj = json.loads(data.decode())
                flights = json_obj['stats']['flights']
                self.epoch = json_obj['stats']['epoch']
                self.connection_alive = True
                return flights
            else:
                logger.error("[ModeSMixer] unexpected HTTP response: {:d}".format(res.code))

        except (ConnectionRefusedError, OSError) as err:
            logger.error(err)

        if conn:
            conn.close()
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

    def query_live_flights(self, filter_incomplete=True):
        """ 
        Retrieve active Mode-S adresses with current properties

        Returns:
            A list of tuples with active flights

        Args:
            filter_incomplete (bool): filter flights w/o positional information
        
        """

        flight_data = self.get_flight_info()

        if flight_data:
            flights = []

            for flight in flight_data:
  
                if ('LA' in flight and 'LO' in flight and 'A') in flight or 'CS' in flight:

                    icao24 = str(flight['I'])
                    lat = flight['LA'] if 'LA' in flight and flight['LA'] else None
                    lon = flight['LO'] if 'LO' in flight and flight['LO'] else None
                    alt = flight['A'] if 'A' in flight and flight['A'] else None
                    callsign = flight['CS'] if 'CS' in flight and flight['CS'] else None

                    if (lat and lon or alt) or (not filter_incomplete and callsign):
                        flights.append((icao24, lat, lon, alt, callsign))

            return flights
        else:
            return None

    #def query_callsign(self, modeS):


    def get_silhouete_params(self):
        return {
            'prefix': "{:s}/img/silhouettes/".format(self._url_parms.geturl()),
            'suffix': ".bmp"
        }

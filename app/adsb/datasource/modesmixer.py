
import logging
import requests
from typing import List
from .radarservice import RadarService
from ..util.request_util import disable_urllibs_response_warnings
from ..model.position_report import PositionReport
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

class ModeSMixer(RadarService):

    """ ModeSMixer Queries """

    def __init__(self, url):

        RadarService.__init__(self, url)

        self.headers['Content-type'] = 'application/json'
        self.epoch = 0
        self.session = requests.Session()     

    def _get_request_body(self, force_initial):

        if force_initial:
            self.epoch = 0

        return {
            "req": "getStats",
            "data": {
                "statsType": "flights", 
                "id": (0 if force_initial else self.epoch)
            }
        }

    @disable_urllibs_response_warnings #modesmixer2 returns RFC 7230 incompliant response headers
    def get_flight_info(self, force_initial=False):

        try:
            # Workaround: urllib3 complains about modesmixer2's response headers, disable warnings for this request 

            msg_body = self._get_request_body(force_initial)

            url = RadarService._urljoin(self.base_path, 'json')
            response = self.session.post(url, json=msg_body, headers=self.headers, timeout=2.0)
            response.raise_for_status()

            json_obj = response.json()
            flights = json_obj['stats']['flights']
            self.epoch = json_obj['stats']['epoch']
            self.connection_alive = True

            return flights

        except RequestException as req_excpt:
            logger.error("[ModeSMixer]: {:s}".format(str(req_excpt)))

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

    @disable_urllibs_response_warnings #modesmixer2 returns RFC 7230 incompliant response headers
    def query_live_flights(self, filter_incomplete=True) -> List[PositionReport]:
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
                    track = flight['T'] if 'T' in flight and flight['T'] else None

                    if (lat and lon or alt) or (not filter_incomplete and callsign):
                        flights.append(PositionReport(icao24, lat, lon, alt, track, callsign))

            return flights
        else:
            return None

    def get_silhouete_params(self):
        return {
            'prefix': "{:s}/img/silhouettes/".format(self._url_parms.geturl()),
            'suffix': ".bmp"
        }

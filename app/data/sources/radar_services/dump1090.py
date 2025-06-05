
import logging
import requests
from typing import List
from ..base import RadarService
from ....core.utils.request_util import disable_urllibs_response_warnings
from ....core.utils.modes_util import ModesUtil
from ....core.models.position_report import PositionReport
from requests.exceptions import RequestException
from datetime import datetime

logger = logging.getLogger(__name__)

class Dump1090(RadarService):

    """ Dump1090 Queries """

    def __init__(self, url):

        RadarService.__init__(self, url)
        self.session = requests.Session()     

    def get_flight_info(self, force_initial=False):

        try:

            url = RadarService._urljoin(self.base_path, 'data/aircraft.json?_={}'.format(self.get_current_timestamp()))
            response = self.session.get(url, headers=self.headers, timeout=2.0)
            response.raise_for_status()

            json_obj = response.json()
            flights = json_obj['aircraft']
            self.connection_alive = True

            return flights

        except RequestException as req_excpt:
            logger.error("[Dump1090]: {:s}".format(str(req_excpt)))

        return None

    def query_live_icao24(self):

        flight_data = self.get_flight_info()

        if flight_data:
            hexcodes = []
            for fl in flight_data:
                if fl:
                    icaohex = str(fl['hex'])
                    hexcodes.append(icaohex)
            return hexcodes
        else:
            return None

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
  
                if ('lat' in flight and 'lon' in flight) or 'flight' in flight:

                    icao24 = flight['hex'].strip()
                    if ModesUtil.is_icao24_addr(icao24):
                        lat = flight['lat'] if 'lat' in flight and flight['lat'] else None
                        lon = flight['lon'] if 'lon' in flight and flight['lon'] else None
                        alt = flight['alt_geom'] if 'alt_geom' in flight and flight['alt_geom'] else None
                        gs = flight['gs'] if 'gs' in flight and flight['gs'] else None
                        track = flight['track'] if 'track' in flight and flight['track'] else None
                        callsign = flight['flight'].strip() if 'flight' in flight and flight['flight'] else None

                        if (lat and lon or alt) or (not filter_incomplete and callsign):
                            flights.append(PositionReport(icao24, lat, lon, alt, gs, track, callsign))

            return flights
        else:
            return None

    def get_silhouete_params(self):
        return {
            'prefix': "{:s}/img/silhouettes/".format(self._url_parms.geturl()),
            'suffix': ".bmp"
        }
    
    def get_current_timestamp(self):
        return int((datetime.now() - datetime(1970, 1, 1)).total_seconds())

import requests
from requests.exceptions import HTTPError
import logging
from typing import Optional

from ..aircraft import Aircraft
from .aircraft_metadata_source import AircraftMetadataSource

logger = logging.getLogger('HexdbIo')


class HexdbIo(AircraftMetadataSource):

    """ HexDB.io Aircraft Database """

    def __init__(self) -> None:

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        self.timeout = 5.0
        self.maxretries = 3

    @staticmethod
    def name() -> str:
        return 'HexDB.io'

    def accept(self, modes_address: str) -> bool:
        return True

    def query_aircraft(self, mode_s_hex: str) -> Optional[Aircraft]:
        """ queries aircraft data from hexdb.io """

        try:
            url = f'https://hexdb.io/api/v1/aircraft/{mode_s_hex}'
            response = requests.get(url, headers=self.headers, timeout=self.timeout)

            if response.status_code == requests.codes.not_found:
                return None

            response.raise_for_status()

            aircraft_data = response.json()

            if aircraft_data:
                mode_s = aircraft_data.get('ModeS', mode_s_hex).upper()
                reg = aircraft_data.get('Registration')
                type1 = aircraft_data.get('ICAOTypeCode')
                
                # Build type2 from manufacturer and type
                manufacturer = aircraft_data.get('Manufacturer', '')
                aircraft_type = aircraft_data.get('Type', '')
                
                if manufacturer and aircraft_type:
                    type2 = f"{manufacturer} {aircraft_type}"
                elif manufacturer:
                    type2 = manufacturer
                elif aircraft_type:
                    type2 = aircraft_type
                else:
                    type2 = None

                operator = aircraft_data.get('RegisteredOwners')

                # Only return aircraft if we have at least registration or type info
                if reg or type1 or type2:
                    return Aircraft(mode_s, reg, type1, type2, operator, source=self.name())

        except HTTPError as http_err:
            if http_err.response.status_code == requests.codes.too_many:
                logger.warning(f'HTTP 429 - Too many requests for {mode_s_hex}')
            else:
                logger.exception(http_err)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            logger.exception('An unexpected error occurred')

        return None
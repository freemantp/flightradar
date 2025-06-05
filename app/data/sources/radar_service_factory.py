from .radar_services.virtualradarserver import VirtualRadarServer
from .radar_services.dump1090 import Dump1090

class RadarServiceFactory:
    @staticmethod
    def create(config):
        """Create appropriate radar service based on configuration"""
        if config.RADAR_SERVICE_TYPE == 'vrs':
            return VirtualRadarServer(config.RADAR_SERVICE_URL)
        elif config.RADAR_SERVICE_TYPE == 'dmp1090':
            return Dump1090(config.RADAR_SERVICE_URL)
        else:
            raise ValueError('Service type not specified in config')
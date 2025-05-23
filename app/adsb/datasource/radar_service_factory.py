from .modesmixer import ModeSMixer
from .virtualradarserver import VirtualRadarServer
from .dump1090 import Dump1090

class RadarServiceFactory:
    @staticmethod
    def create(config):
        """Create appropriate radar service based on configuration"""
        if config.RADAR_SERVICE_TYPE == 'mm2':
            return ModeSMixer(config.RADAR_SERVICE_URL)
        elif config.RADAR_SERVICE_TYPE == 'vrs':
            return VirtualRadarServer(config.RADAR_SERVICE_URL)
        elif config.RADAR_SERVICE_TYPE == 'dmp1090':
            return Dump1090(config.RADAR_SERVICE_URL)
        else:
            raise ValueError('Service type not specified in config')
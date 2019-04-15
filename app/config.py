import json
import os
from pathlib import Path

class Config():

    """ Application configuration """

    DATA_FOLDER = 'resources/'
    RADAR_SERVICE_URL = 'http://flightlive.gotdns.ch:8084/VirtualRadar'
    RADAR_SERVICE_TYPE = 'vrs'
    MILTARY_ONLY = False
    DB_RETENTION_MIN = 1440

    def __init__(self):

        CONFIG_FILE_PATH = 'config.json'

        config_file = Path(CONFIG_FILE_PATH)
        if config_file.is_file():
            self.from_file(CONFIG_FILE_PATH)
        
        self.from_env()

    def str2bool(v):
        return v.lower() in ("yes", "true", "t", "1")

    def sanitize_url(self, url):
        return url[:-1] if url[-1] == "/" else url

    def from_env(self):

        ENV_DATA_FOLDER = 'DATA_FOLDER'
        ENV_RADAR_SERVICE_URL = 'SERVICE_URL'
        ENV_RADAR_SERVICE_TYPE = 'SERVICE_TYPE'
        ENV_MIL_ONLY = 'MIL_ONLY'
        ENV_DB_RETENTION_MIN = 'DB_RETENTION_MIN'

        if os.environ.get(ENV_DATA_FOLDER):
            self.DATA_FOLDER = os.environ.get(ENV_DATA_FOLDER)
        if os.environ.get(ENV_RADAR_SERVICE_URL):
            self.RADAR_SERVICE_URL = self.sanitize_url(os.environ.get(ENV_RADAR_SERVICE_URL))
        if os.environ.get(ENV_RADAR_SERVICE_TYPE):
            self.RADAR_SERVICE_TYPE = os.environ.get(ENV_RADAR_SERVICE_TYPE)
        if os.environ.get(ENV_MIL_ONLY):
            self.MILTARY_ONLY = str2bool(os.environ.get(ENV_MIL_ONLY))
        if os.environ.get(ENV_DB_RETENTION_MIN):
            try:
                self.DB_RETENTION_MIN = int(os.environ.get(ENV_DB_RETENTION_MIN))
            except ValueError:
                pass

    def from_file(self, filename):
        with open(filename, 'r') as json_file:
            config = json.load(json_file)

            if 'dataFolder' in config:
                self.DATA_FOLDER = config['dataFolder']
            else:
                raise ValueError('dataFolder not specified in config')

            if 'type' in config:
                self.RADAR_SERVICE_TYPE = config['type']
            else:
                raise ValueError('type not specified in config')

            if 'serviceUrl' in config:
                self.RADAR_SERVICE_URL = self.sanitize_url(config['serviceUrl'])

            if 'militaryOnly' in config:
                self.MILTARY_ONLY = config['militaryOnly']

            if 'dbRetentionMinutes' in config:
                self.DB_RETENTION_MIN = config['dbRetentionMinutes']

    def __str__(self):
        return 'DATA_FOLDER: {0}, RADAR_SERVICE_URL: {1}, type: {2}, mil_only: {3}, delete_after: {4}'.format(self.DATA_FOLDER, self.RADAR_SERVICE_URL, self.RADAR_SERVICE_TYPE, self.MILTARY_ONLY, self.DB_RETENTION_MIN) 

class DevConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    pass
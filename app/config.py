import json
import os
from pathlib import Path

class Config():

    """ Application configuration """

    DATA_FOLDER = ''
    RADAR_SERVICE_URL = ''
    RADAR_SERVICE_TYPE = ''
    MILTARY_ONLY = False
    DB_RETENTION_MIN = 1440

    def __init__(self):

        CONFIG_FILE_PATH = 'config.json'

        config_file = Path(CONFIG_FILE_PATH)
        print(config_file.absolute())
        if config_file.is_file():
            self.from_file(CONFIG_FILE_PATH)
        else:
            self.from_env()

    def from_env(self):
        self.DATA_FOLDER = os.environ.get('DATA_FOLDER') or 'resources/'
        self.RADAR_SERVICE_URL = os.environ.get('SERVICE_URL') or 'http://flightlive.gotdns.ch:8084/VirtualRadar'
        self.RADAR_SERVICE_TYPE = os.environ.get('SERVICE_TYPE') or 'vrs'

        # TODO: there's probably a lib to to this
        mil_only_env =  os.environ.get('MIL_ONLY')
        if mil_only_env and mil_only_env.lower() in ['true', 'false']:
            self.MILTARY_ONLY = mil_only_env.lower() == 'true'
        else:
            self.MILTARY_ONLY = True

        db_rentention_env = os.environ.get('DB_RETENTION_MIN')
        self.DB_RETENTION_MIN = int(db_rentention_env) if db_rentention_env else 1440

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
                url = config['serviceUrl']
                self.RADAR_SERVICE_URL = url[:-1] if url[-1] == "/" else url

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
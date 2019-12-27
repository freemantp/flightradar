import json
import os
import logging
from pathlib import Path

class LoggingConfig:

    syslogHost = None
    syslogFormat = None
    logLevel = logging.INFO
    logToConsole = True

    @staticmethod
    def from_json(json):
        syslogHost = json['syslogHost']
        syslogFormat = json['syslogFormat']
        logToConsole = True
        logLevel = logging.INFO

        if not syslogHost or not syslogFormat:
            raise ValueError('Incomplete logging config')     

        if 'logLevel' in json:
            logLevel = logging.getLevelName(json['logLevel'].strip().upper())

        if 'logToConsole' in json:
            logToConsole = json['logToConsole']

        return LoggingConfig(syslogHost, syslogFormat, logToConsole, logLevel)

    def __init__(self, syslogHost, syslogFormat, logToConsole=True, logLevel=logging.INFO):
        self.syslogHost = syslogHost
        self.syslogFormat = syslogFormat
        self.logLevel = logLevel
        self.logToConsole = logToConsole

class Config:

    """ Application configuration """

    DATA_FOLDER = 'resources'
    RADAR_SERVICE_URL = 'http://flightlive.gotdns.ch:8084/VirtualRadar'
    RADAR_SERVICE_TYPE = 'vrs'
    MILTARY_ONLY = False
    DB_RETENTION_MIN = 1440
    LOGGING_CONFIG = None
    UNKNOWN_AIRCRAFT_CRAWLING = False
    GOOGLE_MAPS_API_KEY = 'DUMMY_KEY'

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
        ENV_UNKNOWN_AIRCRAFT_CRAWLING = 'UNKNOWN_AIRCRAFT_CRAWLING'
        ENV_GOOGLE_MAPS_API_KEY = 'DUMMY_KEY'

        if os.environ.get(ENV_DATA_FOLDER):
            self.DATA_FOLDER = os.environ.get(ENV_DATA_FOLDER)
        if os.environ.get(ENV_RADAR_SERVICE_URL):
            self.RADAR_SERVICE_URL = self.sanitize_url(os.environ.get(ENV_RADAR_SERVICE_URL))
        if os.environ.get(ENV_RADAR_SERVICE_TYPE):
            self.RADAR_SERVICE_TYPE = os.environ.get(ENV_RADAR_SERVICE_TYPE)
        if os.environ.get(ENV_MIL_ONLY):
            self.MILTARY_ONLY = str2bool(os.environ.get(ENV_MIL_ONLY))
        if os.environ.get(ENV_UNKNOWN_AIRCRAFT_CRAWLING):
            self.UNKNOWN_AIRCRAFT_CRAWLING = str2bool(os.environ.get(ENV_UNKNOWN_AIRCRAFT_CRAWLING))
        if os.environ.get(ENV_GOOGLE_MAPS_API_KEY):
            self.GOOGLE_MAPS_API_KEY = os.environ.get(ENV_GOOGLE_MAPS_API_KEY)
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

            if 'crawlUnknownAircraft' in config:
                self.UNKNOWN_AIRCRAFT_CRAWLING = config['crawlUnknownAircraft']                

            if 'deleteAfterMinutes' in config:
                self.DB_RETENTION_MIN = config['deleteAfterMinutes']

            if 'googleMapsApiKey' in config:
                self.GOOGLE_MAPS_API_KEY = config['googleMapsApiKey']                

            if 'logging' in config:
                try:
                    self.LOGGING_CONFIG = LoggingConfig.from_json(config['logging'])
                except ValueError as e:
                    logging.getLogger().error(e)

    def __str__(self):
        return 'data folder: {0}, service url: {1}, type: {2}, mil only: {3}, delete after: {4}, crawling: {5}, google maps apikey: {6}'.format(self.DATA_FOLDER, self.RADAR_SERVICE_URL, self.RADAR_SERVICE_TYPE, self.MILTARY_ONLY, self.DB_RETENTION_MIN, self.UNKNOWN_AIRCRAFT_CRAWLING, self.GOOGLE_MAPS_API_KEY) 

class DevConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    pass

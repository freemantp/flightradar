import json
import os
import logging
from enum import Enum
from pathlib import Path

logger = logging.getLogger("Config")

class AppState:
    mongodb = None
    
app_state = AppState()

class LoggingConfig:

    syslogHost = None
    syslogFormat = None
    logToConsole = True

    @staticmethod
    def from_json(json):
        logToConsole = True
        logLevel = logging.INFO
        syslogHost = json['syslogHost'] if 'syslogHost' in json else None
        syslogFormat = json['syslogFormat'] if 'syslogFormat' in json else None
        
        if 'logLevel' in json:
            logLevel = logging.getLevelName(json['logLevel'].strip().upper())

        if bool(syslogHost) != bool(syslogFormat):
            raise ValueError('Incomplete logging config')     

        if 'logToConsole' in json:
            logToConsole = json['logToConsole']

        return LoggingConfig(syslogHost, syslogFormat, logToConsole, logLevel)

    def __init__(self, syslogHost, syslogFormat, logToConsole=True, logLevel=logging.INFO):
        self.syslogHost = syslogHost
        self.syslogFormat = syslogFormat
        self.logLevel = logLevel
        self.logToConsole = logToConsole

class ConfigSource(Enum):
    NONE = 0
    FILE = 1
    ENV = 2

class Config:

    """ Application configuration """

    DATA_FOLDER = 'resources'
    RADAR_SERVICE_URL = 'http://flightlive.gotdns.ch:8084/VirtualRadar'
    RADAR_SERVICE_TYPE = 'vrs'
    MILTARY_ONLY = False
    DB_RETENTION_MIN = 1440
    LOGGING_CONFIG = None
    UNKNOWN_AIRCRAFT_CRAWLING = False
    
    # Database configuration
    MONGODB_URI = 'mongodb://localhost:27017/'
    MONGODB_DB_NAME = 'flightradar'

    def __init__(self, config_file='config.json'):

        self.config_src = ConfigSource.NONE

        config_file = Path(config_file)
        if config_file.is_file():
            self.from_file(config_file)
        else:
            self.from_env()

        if self.config_src == ConfigSource.NONE:
            raise ValueError('Configuration is neither read from env nor file')
        else:
            logger.info('Config loaded from source: {}'.format(self.config_src.name))

    def str2bool(self, v):
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
        ENV_LOGGING_CONFIG = 'LOGGING_CONFIG'
        ENV_MONGODB_URI = 'MONGODB_URI'
        ENV_MONGODB_DB_NAME = 'MONGODB_DB_NAME'

        if os.environ.get(ENV_DATA_FOLDER):
            self.DATA_FOLDER = os.environ.get(ENV_DATA_FOLDER)
        if os.environ.get(ENV_RADAR_SERVICE_URL):
            self.RADAR_SERVICE_URL = self.sanitize_url(os.environ.get(ENV_RADAR_SERVICE_URL))
        if os.environ.get(ENV_RADAR_SERVICE_TYPE):
            self.RADAR_SERVICE_TYPE = os.environ.get(ENV_RADAR_SERVICE_TYPE)        
        if os.environ.get(ENV_MIL_ONLY):
            self.MILTARY_ONLY = self.str2bool(os.environ.get(ENV_MIL_ONLY))
        if os.environ.get(ENV_UNKNOWN_AIRCRAFT_CRAWLING):
            self.UNKNOWN_AIRCRAFT_CRAWLING = self.str2bool(os.environ.get(ENV_UNKNOWN_AIRCRAFT_CRAWLING))
        if os.environ.get(ENV_DB_RETENTION_MIN):
            try:
                self.DB_RETENTION_MIN = int(os.environ.get(ENV_DB_RETENTION_MIN))
            except ValueError:
                pass
        if os.environ.get(ENV_LOGGING_CONFIG):
            try:
                logging_json = json.loads(os.environ.get(ENV_LOGGING_CONFIG))
                self.LOGGING_CONFIG = LoggingConfig.from_json(logging_json)
            except ValueError as e:
                logging.getLogger().error(e)
        if os.environ.get(ENV_MONGODB_URI):
            self.MONGODB_URI = os.environ.get(ENV_MONGODB_URI)
        if os.environ.get(ENV_MONGODB_DB_NAME):
            self.MONGODB_DB_NAME = os.environ.get(ENV_MONGODB_DB_NAME)
        self.config_src = ConfigSource.ENV

    def from_file(self, filename):
        with open(filename, 'r') as json_file:
            config = json.load(json_file)

            if 'dataFolder' in config:
                self.DATA_FOLDER = config['dataFolder']
            else:
                raise ValueError('dataFolder not specified in config')

            if 'type' in config:
                self.RADAR_SERVICE_TYPE = config['type']

            if 'serviceUrl' in config:
                self.RADAR_SERVICE_URL = self.sanitize_url(config['serviceUrl'])

            if 'militaryOnly' in config:
                self.MILTARY_ONLY = config['militaryOnly']

            if 'crawlUnknownAircraft' in config:
                self.UNKNOWN_AIRCRAFT_CRAWLING = config['crawlUnknownAircraft']                

            if 'deleteAfterMinutes' in config:
                self.DB_RETENTION_MIN = config['deleteAfterMinutes']  

            if 'logging' in config:
                try:
                    self.LOGGING_CONFIG = LoggingConfig.from_json(config['logging'])
                except ValueError as e:
                    logging.getLogger().error(e)
                    
            if 'database' in config:
                db_config = config['database']
                if 'mongodb_uri' in db_config:
                    self.MONGODB_URI = db_config['mongodb_uri']
                if 'mongodb_db_name' in db_config:
                    self.MONGODB_DB_NAME = db_config['mongodb_db_name']

            self.config_src = ConfigSource.FILE

    def __str__(self):
        return 'data folder: {0}, service url: {1}, type: {2}, mil only: {3}, delete after: {4}, crawling: {5}'.format(self.DATA_FOLDER, self.RADAR_SERVICE_URL, self.RADAR_SERVICE_TYPE, self.MILTARY_ONLY, self.DB_RETENTION_MIN, self.UNKNOWN_AIRCRAFT_CRAWLING) 

class DevConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    pass
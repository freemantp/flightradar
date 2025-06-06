import unittest
from test import support

from app.config import Config, ConfigSource, LoggingConfig


class ConfigTest(unittest.TestCase):

    def test_env_fallback(self):
        "Test fallback to env when config file is missing"

        with support.EnvironmentVarGuard() as env:
            env.set('DATA_FOLDER','someresource')
            env.set('SERVICE_URL','http://path/to/service')
            env.set('SERVICE_TYPE','srvtype')
            env.set('MIL_ONLY','true')
            env.set('DB_RETENTION_MIN','999')
            env.set('UNKNOWN_AIRCRAFT_CRAWLING','true')
            env.set('LOGGING_CONFIG', '{\"syslogHost\":\"log.server.com\",\"syslogFormat\":\"logformat:[%(name)s]%(message)s\",\"logLevel\":\"INFO\",\"logToConsole\":true}')      

            config = Config('/path/tononexistent.json')
            self.assertEqual(ConfigSource.ENV, config.config_src)
            self.assertEqual('someresource', config.DATA_FOLDER)
            self.assertEqual('http://path/to/service', config.RADAR_SERVICE_URL)
            self.assertEqual('srvtype', config.RADAR_SERVICE_TYPE)
            self.assertEqual(True, config.MILTARY_ONLY)
            self.assertEqual(999, config.DB_RETENTION_MIN)
            self.assertEqual(True, config.UNKNOWN_AIRCRAFT_CRAWLING)
            self.assertTrue(isinstance(config.LOGGING_CONFIG, LoggingConfig) )

    
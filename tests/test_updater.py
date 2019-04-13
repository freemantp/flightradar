import unittest

from app.adsb.flightupdater import FlightUpdater
from app.adsb.config import Config

class FlightUpdaterTest(unittest.TestCase):

    def setUp(self):
        conf = Config()
        conf.from_file('config.json')
        self.sut = FlightUpdater.Instance()
        self.sut.initialize(conf)

    def test_add_position(self):

        icao = 'AB2345'

        # self.sut.add_positions(icao, (1.1, 2.2, 999))
        # self.sut.add_positions(icao, (1.1, 2.2, 999))
        # self.sut.add_positions(icao, (1.1, 2.3, 999))
        # self.sut.add_positions(icao, (1.1, 2.3, 999))
        # entries = self.sut.get_entry(icao)
        # self.assertEqual(len(entries.pos), 2)


if __name__ == '__main__':
    unittest.main()
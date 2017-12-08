import unittest

from updateThread import UpdaterThread
from adsb.config import Config

class TestADSB(unittest.TestCase):

    def test_add_position(self):

        conf = Config()
        conf.from_file('config.json')
        updater = UpdaterThread(conf)

        icao = 'AB2345'

        updater.update_data(icao, (1.1, 2.2, 999))
        updater.update_data(icao, (1.1, 2.2, 999))
        updater.update_data(icao, (1.1, 2.3, 999))
        updater.update_data(icao, (1.1, 2.3, 999))
        entries = updater.get_entry(icao)
        self.assertEqual(len(entries.pos), 2)


if __name__ == '__main__':
    unittest.main()
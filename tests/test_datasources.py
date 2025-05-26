import unittest

from app.adsb.datasource.bazllfr import BazlLFR
from app.adsb.datasource.militarymodes_eu import MilitaryModeS
from app.adsb.datasource.openskynet import OpenskyNet
from app.adsb.datasource.flightradar24 import Flightradar24
from app.adsb.datasource.secret_base import SecretBasesUk
from app.adsb.datasource.hexdb_io import HexdbIo

class ModeSUtilTests(unittest.TestCase):

    def setUp(self):
        self.civilian_hex = '4B19F3'
        self.military_hex = '3B76B3'
        self.military_hex2 = '3F45F3'

    def test_bazl_lfr(self):
        sut = BazlLFR()
        aircraft = sut.query_aircraft(self.civilian_hex)
        self.assertIsNotNone(aircraft)
        self.assertTrue(aircraft.is_complete2())

    @unittest.skip("This service is flaky")
    def test_militarymodes_eu(self):
        sut = MilitaryModeS('resources')
        aircraft = sut.query_aircraft(self.military_hex2)
        self.assertIsNotNone(aircraft)
        self.assertTrue(aircraft.has_type())

    def test_openskynet(self):
        sut = OpenskyNet()
        aircraft = sut.query_aircraft(self.civilian_hex)
        self.assertIsNotNone(aircraft)
        self.assertTrue(aircraft.is_complete2())

    def test_flightradar24(self):
        sut = Flightradar24()
        aircraft = sut.query_aircraft(self.civilian_hex)
        self.assertIsNotNone(aircraft)
        self.assertTrue(aircraft.is_complete2())  

    @unittest.skip("This service is flaky")
    def test_secretbase(self):
        sut = SecretBasesUk('resources')
        aircraft = sut.query_aircraft(self.military_hex)
        self.assertIsNotNone(aircraft)
        self.assertTrue(aircraft.is_complete2())

    def test_hexdb_io(self):
        sut = HexdbIo()
        aircraft = sut.query_aircraft(self.civilian_hex)
        self.assertIsNotNone(aircraft)
        self.assertTrue(aircraft.has_type() or aircraft.reg is not None)

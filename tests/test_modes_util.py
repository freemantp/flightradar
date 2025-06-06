import unittest

from app.core.utils.modes_util import ModesUtil

class ModeSUtilTests(unittest.TestCase):

    def setUp(self):
        self.sut = ModesUtil('resources/')

    def tearDown(self):
        self.sut = None

    def test_mil_modes(self):
        self.assertTrue(self.sut.is_military('3B76B3'))

    def test_nonmil_modes(self):
        self.assertFalse(self.sut.is_military('4D010C'))

    def test_swiss(self):
        self.assertTrue(self.sut.is_swiss('4B1A5F'))

    def test_non_swiss(self):
        self.assertFalse(self.sut.is_swiss('3003AD'))

    def test_mil_swiss(self):
        self.assertTrue(self.sut.is_swiss_mil(0x4B7F45))

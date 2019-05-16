import unittest
import time

from app.adsb.flightupdater import FlightUpdater
from app.adsb.db.dbmodels import Position, Flight
from app.config import Config
from db_base_test import DbBaseTestCase


class MockRadarService:

    connection_alive = False
    flights = []

    def query_live_flights(self, incomplete):
        return self.flights


class FlightUpdaterTest(DbBaseTestCase):

    def setUp(self):
        DbBaseTestCase.setUp(self)
        self.sut = FlightUpdater.Instance()
        self.sut.initialize(Config())
        self.sut._mil_only = False
        self.sut._service = MockRadarService()

    def tearDown(self):
        DbBaseTestCase.tearDown(self)

    def test_update(self):
        "Test flight/position insertion"
        self.sut._service.flights = [
            ('12345', 41.1, 60.1, 1723, 'CLLSGN'),
            ('12345', 44.1, 63.1, 1723, None),
        ]

        self.sut.update()

        self.assertEqual(1, Flight.select().count())
        self.assertEqual('CLLSGN', Flight.select().first().callsign)
        self.assertEqual(2, Position.select().count())

    def test_update_no_duplicate(self):
        """Test duplicate elimination"""
        self.sut._service.flights = [
            ('12345', 41.1, 60.1, 1723, 'CLLSGN'),
            ('12345', 44.1, 63.1, 1723, None)
        ]

        self.sut.update()

        self.sut._service.flights = [
            ('12345', 44.1, 63.1, 1723, None)
        ]

        self.sut.update()

        self.assertEqual(2, Position.select().count())

    def test_cleanup(self):
        """ Test stale flight / position cleanup"""
        self.sut._service.flights = [
            ('12345', 41.1, 60.1, 1723, 'CLLSGN'),
            ('12345', 44.1, 63.1, 1723, None)
        ]

        self.sut.update()
        
        time.sleep(1.1)

        self.sut._delete_after = float(1 / 60)
        self.sut.cleanup_items()

        self.assertEqual(0, Position.select().count())
        self.assertEqual(0, Flight.select().count())
        self.assertFalse(self.sut.modeS_flight_map)
        self.assertFalse(self.sut.flight_lastpos_map)
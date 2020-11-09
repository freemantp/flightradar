import unittest
import time
from typing import List
from flask import Flask

from app.adsb.flightupdater import FlightUpdater
from app.adsb.db.dbmodels import Position, Flight
from app.config import Config
from db_base_test import DbBaseTestCase
from app.adsb.model.position_report import PositionReport


class MockRadarService:

    connection_alive = False
    flights = []

    def query_live_flights(self, incomplete) -> List[PositionReport]:
        return self.flights

class MockModeSUtil:

    def is_military(self, modeS):
        return False


class FlightUpdaterTest(DbBaseTestCase):

    def setUp(self):
        DbBaseTestCase.setUp(self)
        self.sut = FlightUpdater()
        self.sut.initialize(Config())
        self.sut._mil_only = False
        self.sut._service = MockRadarService()

        self.app = Flask('test')

        def is_military_func(modeS):
            return False

        self.app.modes_util = MockModeSUtil()

        print('dsfdf')

    def tearDown(self):
        DbBaseTestCase.tearDown(self)

    def test_update(self):
        "Test flight/position insertion"
        self.sut._service.flights = [
            PositionReport('12345', 41.1, 60.1, 1723, 123, 'CLLSGN'),
            PositionReport('12345', 44.1, 63.1, 1723, 321, None),
        ]

        with self.app.app_context():
            self.sut.update()

        self.assertEqual(1, Flight.select().count())
        self.assertEqual('CLLSGN', Flight.select().first().callsign)
        self.assertEqual(2, Position.select().count())

    def test_update_no_duplicate(self):
        """Test duplicate elimination"""
        self.sut._service.flights = [
            PositionReport('12345', 41.1, 60.1, 1723, 123, 'CLLSGN'),
            PositionReport('12345', 44.1, 63.1, 1723, 321, None)
        ]

        with self.app.app_context():
            self.sut.update()

            self.sut._service.flights = [
                PositionReport('12345', 44.1, 63.1, 1723, 321, None)
            ]

            self.sut.update()

        self.assertEqual(2, Position.select().count())

    def test_cleanup(self):
        """ Test stale flight / position cleanup"""
        self.sut._service.flights = [
            PositionReport('12345', 41.1, 60.1, 1723, 123, 'CLLSGN'),
            PositionReport('12345', 44.1, 63.1, 1723, 321, None)
        ]

        self.sut.update()
        
        time.sleep(1.1)

        self.sut._delete_after = float(1 / 60)
        self.sut.cleanup_items()

        self.assertEqual(0, Position.select().count())
        self.assertEqual(0, Flight.select().count())
        self.assertFalse(self.sut.modeS_flightid_map)
        self.assertFalse(self.sut.flight_lastpos_map)

    def test_initialize_db(self):
        """ Test initialization from db"""

        self.assertFalse(self.sut.modeS_flightid_map)
        self.assertFalse(self.sut.flight_lastpos_map)

        id1 = Flight.insert(modeS='4B2241',callsign='CLLSGN').execute()
        id2 = Flight.insert(modeS='F1A2C0',callsign='OTHRCS').execute()
        Position.insert(flight_fk=id1, lat=41.1, lon=60.1, alt=1723).execute()
        Position.insert(flight_fk=id2, lat=44.1, lon=63.1, alt=1923).execute()

        self.sut._initialize_from_db()
        
        self.assertEqual(id1, self.sut.modeS_flightid_map['4B2241'])
        self.assertEqual(id2, self.sut.modeS_flightid_map['F1A2C0'])
        self.assertEqual((id1,41.1,60.1,1723), self.sut.flight_lastpos_map[id1])
        self.assertEqual((id2,44.1,63.1,1923), self.sut.flight_lastpos_map[id2])


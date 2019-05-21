import unittest
import time

from app.adsb.db.dbmodels import Position, Flight

from app.adsb.db.dbrepository import DBRepository
from db_base_test import DbBaseTestCase


class DBRepositoryTest(DbBaseTestCase):

    def test_delete(self):
        "Test flight deletion"

        id1 = Flight.insert(modeS='4B2241',callsign='CLLSGN').execute()
        id2 = Flight.insert(modeS='F1A2C0',callsign='OTHRCS').execute()
        Position.insert(flight_fk=id1, lat=41.1, lon=60.1, alt=1723).execute()
        Position.insert(flight_fk=id2, lat=44.1, lon=63.1, alt=1923).execute()

        DBRepository.delete_flights_and_positions([id1, id2])

        self.assertEqual(0, Flight.select().count())
        self.assertEqual(0, Position.select().count())


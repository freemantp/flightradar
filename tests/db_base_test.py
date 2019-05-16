import unittest

from peewee import SqliteDatabase

from app.adsb.db.dbmodels import Position, Flight
from app.config import Config

test_db = SqliteDatabase(':memory:')
MODELS = [Flight, Position]

class DbBaseTestCase(unittest.TestCase):

    def setUp(self):
        test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        test_db.connect()
        test_db.create_tables(MODELS)

    def tearDown(self):
        test_db.drop_tables(MODELS)
        test_db.close()        
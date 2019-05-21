import unittest

from peewee import SqliteDatabase

from app.adsb.db.dbmodels import Position, Flight, database_proxy
from app.config import Config

test_db = SqliteDatabase(':memory:')
MODELS = [Flight, Position]

class DbBaseTestCase(unittest.TestCase):

    def setUp(self):
        test_db.bind(MODELS, bind_refs=False, bind_backrefs=False)
        test_db.connect()
        test_db.create_tables(MODELS)
        database_proxy.initialize(test_db)

    def tearDown(self):
        database_proxy.initialize(None)
        test_db.drop_tables(MODELS)
        test_db.close()        
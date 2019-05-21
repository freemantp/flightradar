from peewee import SqliteDatabase, Model, DatabaseProxy
from peewee import AutoField, CharField, FixedCharField, FloatField
from peewee import BooleanField, DateTimeField, IntegerField, ForeignKeyField
import datetime
from os import path

database_proxy = DatabaseProxy()

class BaseModel(Model):
    class Meta:
        database = database_proxy

class Flight(BaseModel):
    id = AutoField
    callsign = CharField(null = True)
    modeS = FixedCharField(max_length=6, index=True)
    archived = BooleanField(default=False)
    first_contact = DateTimeField(default=datetime.datetime.utcnow)
    last_contact = DateTimeField(default=datetime.datetime.utcnow)

    def __str__(self):
        return 'Flight id={:d}, callsign={:s}, modeS={:s}, archived={:s}, last_contact={:s}'.format( self.id, str(self.callsign), str(self.modeS), str(self.archived), str(self.last_contact) )

class Position(BaseModel):
    flight_fk = ForeignKeyField(Flight, backref='positions')
    lat = FloatField()
    lon = FloatField()   
    alt = IntegerField(null=True)
    timestmp = DateTimeField(default=datetime.datetime.utcnow)

    class Meta:
        database = database_proxy
        primary_key = False

    def __repr__(self):
        return 'flight={:d} pos=({:f},{:f},{:d}) at={:s}'.format( self.flight_fk.id, self.lat, self.lon, self.alt, str(self.timestmp) )

DB_MODEL_CLASSES = [Flight, Position]

def init_schema(db):

    TRIGGER_CREATE = 'CREATE TRIGGER flight_timestmp_trigger AFTER INSERT ON Position BEGIN UPDATE Flight SET last_contact = NEW.timestmp WHERE id=NEW.flight_fk_id; END'

    db.create_tables(DB_MODEL_CLASSES)
    db.execute_sql(TRIGGER_CREATE)

def init_db(data_folder):

    position_db = SqliteDatabase(
        path.join(data_folder, 'flights.sqlite'),
        pragmas={
            'journal_mode': 'wal',
            'cache_size': -1024 * 32
        })


    database_proxy.initialize(position_db)

    return position_db
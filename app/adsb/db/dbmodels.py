import peewee as pw
import datetime
from os import path

from playhouse.sqliteq import SqliteQueueDatabase

database_proxy = pw.Proxy()

class Flight(pw.Model):
    id = pw.AutoField
    callsign = pw.CharField(null = True)
    modeS = pw.FixedCharField(max_length=6, index=True)
    archived = pw.BooleanField(default=False)
    first_contact = pw.DateTimeField(default=datetime.datetime.utcnow)
    last_contact = pw.DateTimeField(default=datetime.datetime.utcnow)

    class Meta:
        database = database_proxy

    def __str__(self):
        return 'Flight id={:d}, callsign={:s}, modeS={:s}, archived={:s}, last_contact={:s}'.format( self.id, str(self.callsign), str(self.modeS), str(self.archived), str(self.last_contact) )

class Position(pw.Model):
    flight_fk = pw.ForeignKeyField(Flight, backref='positions')
    lat = pw.FloatField()
    lon = pw.FloatField()   
    alt = pw.IntegerField(null=True)
    timestmp = pw.DateTimeField(default=datetime.datetime.utcnow)

    class Meta:
        database = database_proxy
        primary_key = False

    def __repr__(self):
        return 'flight={:d} pos=({:f},{:f},{:d}) at={:s}'.format( self.flight_fk.id, self.lat, self.lon, self.alt, str(self.timestmp) )

DB_MODEL_CLASSES = [Flight, Position]

TRIGGER_CREATE = 'CREATE TRIGGER flight_timestmp_trigger AFTER INSERT ON Position BEGIN UPDATE Flight SET last_contact = NEW.timestmp WHERE id=NEW.flight_fk_id; END'

def init_db_schema(data_folder):

    position_db = SqliteQueueDatabase(
        path.join(data_folder, 'flights.sqlite'),
        use_gevent=False,  # Use the standard library "threading" module.
        autostart=True,  # The worker thread now must be started manually.
        queue_max_size=64,  # Max. # of pending writes that can accumulate.
        results_timeout=5.0)  # Max. time to wait for query to be executed.

    database_proxy.initialize(position_db)

    # TODO: Really do this on startup??
    position_db.create_tables(DB_MODEL_CLASSES) #init db
    position_db.execute_sql(TRIGGER_CREATE)

    return position_db
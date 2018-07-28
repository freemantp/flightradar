import peewee as pw
import datetime

database_proxy = pw.Proxy()

class Flight(pw.Model):
    id = pw.AutoField
    callsign = pw.CharField(null = True)
    modeS = pw.FixedCharField(max_length=6)
    archived = pw.BooleanField(default=False)
    first_contact = pw.DateTimeField(default=datetime.datetime.utcnow)
    last_contact = pw.DateTimeField(default=datetime.datetime.utcnow)

    class Meta:
        database = database_proxy

    def __str__(self):
        return 'Flight id={:d}, callsign={:s}, modeS={:s}, archived={:s}, last_contact={:s}'.format( self.id, str(self.callsign), str(self.modeS), str(self.archived), str(self.last_contact) )

class Position(pw.Model):
    flight_fk = pw.ForeignKeyField(Flight)
    lat = pw.FloatField()
    lon = pw.FloatField()   
    alt = pw.IntegerField(null=True)
    timestmp = pw.DateTimeField(default=datetime.datetime.utcnow)

    class Meta:
        database = database_proxy
        primary_key = False

    def __repr__(self):
        return 'flight={:d} pos=({:f},{:f},{:d}) at={:s}'.format( self.flight_fk, self.lat, self.lon, self.alt, str(self.timestmp) )

#TODO run at create time -> peewee ?
triggger_create = 'CREATE TRIGGER flight_timestamp_trigger AFTER INSERT ON Position BEGIN UPDATE Flight SET last_contact = NEW.timestmp WHERE id=NEW.flight_fk_id; END'

flight_index = "CREATE INDEX 'ModeSaddr_IDX' ON 'flight' ( 'modeS' )"

DB_MODEL_CLASSES = [Flight, Position]
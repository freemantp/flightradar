import peewee as pw
import datetime

database_proxy = pw.Proxy()

class Flight(pw.Model):
    id = pw.AutoField
    callsign = pw.CharField
    modeS = pw.FixedCharField(max_length=6)
    archived = pw.BooleanField(default=False)

    class Meta:
        database = database_proxy

    def __repr__(self):
        return 'Flight id={:d} callsign={:s} modeS={:s} archived={:s]'.format( self.id, self.callsign, self.modeS, self.archived )

class Position(pw.Model):
    flight_fk = pw.ForeignKeyField(Flight)
    lat = pw.FloatField()
    lon = pw.FloatField()
    alt = pw.IntegerField(null=True)
    timestmp = pw.DateTimeField(default=datetime.datetime.utcnow)

    class Meta:
        database = database_proxy

    def __repr__(self):
        return 'flight={:d} pos=({:f},{:f},{:d}) at={:s}'.format( self.flight_fk, self.lat, self.lon, self.alt, str(self.timestmp) )

MODELS = [Flight, Position]
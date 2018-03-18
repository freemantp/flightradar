import peewee as pw
import datetime

database_proxy = pw.Proxy() 

class Position(pw.Model):
    icao = pw.FixedCharField(max_length=6)
    lat = pw.FloatField()
    lon = pw.FloatField()
    alt = pw.IntegerField()
    timestmp = pw.DateTimeField(default=datetime.datetime.utcnow)

    class Meta:
        primary_key = pw.CompositeKey('icao', 'timestmp')
        database = database_proxy

    def __repr__(self):
        return 'Position {:s} ({:f},{:f},{:d}) {:s}'.format( self.icao, self.lat, self.lon, self.alt, str(self.timestmp) )
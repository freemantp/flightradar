import sqlite3
import datetime
import logging

from ..aircraft import Aircraft

logger = logging.getLogger(__name__)

class BaseStationDB:

    """ BaseStationDB """

    def __init__(self, file):
        self.conn = sqlite3.connect(file, isolation_level=None, check_same_thread=False)
        self.cur = self.conn.cursor()

    def __del__(self):
        self.cur.close()
        self.conn.close()

    def query_aircraft(self, icao24addr):
        self.cur.execute("SELECT Registration, ICAOTypeCode, Type, RegisteredOwners FROM Aircraft where ModeS = (?)", (icao24addr.strip().upper(),))
        res = self.cur.fetchone()
        if res:
            return Aircraft(icao24addr, res[0], res[1], res[2], res[3])
        else:
            return None

    def update_aircraft(self, aircraft):
        try:
            if aircraft.is_complete2():
                sql = "UPDATE Aircraft set Registration = (?), ICAOTypeCode = (?), Type = (?), RegisteredOwners = (?) WHERE ModeS = (?);"
                self.cur.execute(sql, (aircraft.reg, aircraft.type1, aircraft.type2, aircraft.operator, aircraft.modes_hex)  )
                return True
            elif aircraft.is_complete():
                sql = "UPDATE Aircraft set Registration = (?), ICAOTypeCode = (?), Type = (?) WHERE ModeS = (?);"
                self.cur.execute(sql, (aircraft.reg, aircraft.type1, aircraft.type2, aircraft.modes_hex)  )
                return True
            elif aircraft.reg:
                sql = "UPDATE Aircraft set Registration = (?) WHERE ModeS = (?);" 
                self.cur.execute(sql, (aircraft.reg, aircraft.modes_hex)  )
                return True
        except sqlite3.OperationalError as oe:
            logger.exception(oe)
            logger.error('Could not update aircraft: {:s}'.format(str(aircraft)))
            return False

    def insert_aircraft(self, acrft):
        if acrft:
            try:
                timestamp = datetime.datetime.now().isoformat()
                sql = "INSERT INTO Aircraft (ModeS,FirstCreated,LastModified,Registration,ICAOTypeCode,Type,RegisteredOwners) VALUES(?,?,?,?,?,?,?);" 
                self.cur.execute(sql, (acrft.modes_hex, timestamp,timestamp,acrft.reg, acrft.type1, acrft.type2, acrft.operator))
                return True
            except (sqlite3.OperationalError, sqlite3.IntegrityError) as oe:
                logger.exception(oe)
                logger.error('Could not insert aircraft: {:s}'.format(str(acrft)))
        
        return False

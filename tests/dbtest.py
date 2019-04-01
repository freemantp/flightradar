import logging
import os
from datetime import datetime, timedelta
from functools import reduce

from flask import Flask
from peewee import *

from adsb.config import Config
from adsb.db.dbmodels import Position, Flight, database_proxy, DB_MODEL_CLASSES
from adsb.db.dbrepository import DBRepository

adsb_config = Config()
adsb_config.from_file('config.json')

db_path = '{:s}/positions.db'.format(adsb_config.data_folder)
logging.info(db_path)

# instantiate the db wrapper
db =  SqliteDatabase(db_path)

database_proxy.initialize(db)

#app = Flask(__name__)

def create_tables():
    with db:
        db.create_tables(DB_MODEL_CLASSES)

def add_positon():
    try:
        with db.transaction():
            Position.create(icao='123456', lat='1.23', lon='4.56', alt='999')

    except IntegrityError:
        print('That pos is already taken')

# Connect to our database.
db.connect()

def split_flightsX(positions):

    """ Splits position data from positions into 'flights' and returns them as lists"""

    flights = []

    if positions:

        fifteen_min = timedelta(minutes=15)
        start_idx = 0       
    
        for i in range(1, len(positions)):
            tdiff = positions[i].timestmp - positions[i-1].timestmp
            if abs(tdiff) > fifteen_min:
                flights.append(positions[start_idx:i])
                start_idx = i
                print(positions[i-1])
                print(positions[i])
                print("--------------")


        flights.append(positions[start_idx:])
    return flights

# query2 = (Position.select()
#             .where(Position.archived == False)
#             .order_by(Position.icao, Position.timestmp.asc()))

# split_list = split_flightsX(query2)

# for lst in split_list:
#     print(list(map(lambda f : f.timestmp.strftime('%H:%M'),lst)))

create_tables()

result_set = Flight.select(Flight.callsign, Flight.modeS, Flight.archived)
    #.order_by(fn.MAX(Flight.timestmp).desc()))

for r in result_set:
    print(r.__data__)

db.close()

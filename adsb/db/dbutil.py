from .dbmodels import Position
from datetime import datetime, timedelta

class DBUtils:

    @staticmethod
    def split_flights(positions):

        """ Splits position data from positions into 'flights' and returns them as lists"""

        flights = []

        if positions:

            fifteen_min = timedelta(minutes=15)
            current_icao = positions[0].icao
            start_idx = 0       
        
            for i in range(1, len(positions)):
                tdiff = positions[i].timestmp - positions[i-1].timestmp
                if abs(tdiff) > fifteen_min or positions[i].icao != current_icao:
                    flights.append(positions[start_idx:i])
                    start_idx = i
                    current_icao = positions[i].icao

            flights.append(positions[start_idx:])
        return flights


    @staticmethod
    def get_flights(icao):
        query = (Position.select().where(Position.icao == icao))
        return DBUtils.split_flights(query)

    @staticmethod
    def get_all_flights(archived=False):

        if archived:
            query = (Position.select()
                             .order_by(Position.icao, Position.timestmp.asc()) )
        else:
            query = (Position.select()
                             .where(Position.archived == False)
                             .order_by(Position.icao, Position.timestmp.asc()))

        return DBUtils.split_flights(query)

        
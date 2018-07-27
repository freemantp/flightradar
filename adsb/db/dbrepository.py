from .dbmodels import Position, Flight
from datetime import datetime, timedelta

class DBRepository:

    @staticmethod
    def split_flights(positions):

        """ Splits position data from positions into 'flights' and returns them as lists"""

        flights = []

        if positions:

            fifteen_min = timedelta(minutes=15)
            current_flight_id = positions[0].flight_fk
            start_idx = 0       
        
            for i in range(1, len(positions)):
                tdiff = positions[i].timestmp - positions[i-1].timestmp
                if abs(tdiff) > fifteen_min or positions[i].flight_fk != current_flight_id:
                    flights.append(positions[start_idx:i])
                    start_idx = i
                    current_flight_id = positions[i].flight_fk

            flights.append(positions[start_idx:])
        return flights


    @staticmethod
    def get_flights(modeS_addr):
        return Flight.select().where(Flight.modeS == modeS_addr)

    @staticmethod
    def get_all_positions(archived=False):

        if archived:
            query = (Position.select()
                             .order_by(Position.flight_fk, Position.timestmp.asc()) )
        else:
            query = (Position.select()
                             #.where(Position.archived == False) TODO: archived?
                             .order_by(Position.flight_fk, Position.timestmp.asc()))

        return DBRepository.split_flights(query) #TODO: flights are already split in db!

    @staticmethod
    def get_positions(flight_id):
        return (Position.select()
                        .where(Position.flight_fk == flight_id)
                        .order_by(Position.flight_fk, Position.timestmp.asc()))

    @staticmethod
    def get_non_archived_flights_older_than(timestamp):
            return Flight.select(Flight.id, Flight.callsign, Flight.last_contact).where((Flight.last_contact < timestamp) & (Flight.archived == False ))
                                                
    @staticmethod
    def delete_flight_and_positions(flight_id):
        Position.delete().where(Position.flight_fk == flight_id).execute()
        Flight.delete().where(Flight.id == flight_id).execute()


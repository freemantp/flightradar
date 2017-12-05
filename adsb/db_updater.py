import time
import json

from .modesmixer import ModeSMixer
from .basestationdb import BaseStationDB
from .flightradar24 import Flightradar24
#import Util.Tabular


class DbUpdater:

    @staticmethod
    def update_live_from_fr24(config):

        fr24_queried = set()
        not_found = set()

        bs_db = BaseStationDB(config.data_folder + "BaseStation.sqb")

        fr24 = Flightradar24()
        msm = ModeSMixer(config.host, config.port)

        while True:

            print("quering modesmixer")
            live_aircraft = msm.query_live_aircraft()
            print("got %d live ones" % len(live_aircraft))
            for hex in live_aircraft:

                aircraft = bs_db.query_aircraft(hex)

                if aircraft and not aircraft.is_complete():

                    if hex not in fr24_queried:
                        print("quering fr24 for %s" % hex)
                        fr24aircraft = fr24.query_aircraft(hex)
                        fr24_queried.add(hex)
                        print("fr24: %s" % fr24aircraft)
                        if fr24aircraft:
                            aircraft.merge(fr24aircraft)
                            updated = bs_db.update_aircraft(aircraft)
                            print("%s  - updated=%s" % (aircraft, updated))
                        else:
                            not_found.add(hex)

                if not aircraft:
                    fr24aircraft = fr24.query_aircraft(hex)
                    fr24_queried.add(hex)
                    if fr24aircraft:
                        inserted = bs_db.insert_aircraft(fr24aircraft)
                        print("%s  - inserted=%s" % (fr24aircraft, inserted))

            print("sleeping")
            time.sleep(20)

    def update_file_from_fr24(config, filename):

        fr24_queried = set()
        not_found = set()
        icaos_from_file = set()

        bs_db = BaseStationDB(config.data_folder + "BaseStation.sqb")

        with open(filename, 'r') as f:
            for line in f:
                icao24 = line.split()[0]
                icaos_from_file.add(icao24)

        fr24 = Flightradar24()
        for hex in icaos_from_file:

            aircraft = bs_db.query_aircraft(hex)

            if aircraft and not aircraft.is_complete():

                if hex not in fr24_queried:
                    print("quering fr24 for %s" % hex)
                    fr24aircraft = fr24.query_aircraft(hex)
                    break
                    fr24_queried.add(hex)
                    print("fr24: %s" % fr24aircraft)
                    if fr24aircraft:
                        aircraft.merge(fr24aircraft)
                        updated = bs_db.update_aircraft(aircraft)
                        print("%s  - updated=%s" % (aircraft,updated))
                    else:
                        not_found.add(hex)

            if not aircraft:
                fr24aircraft = fr24.query_aircraft(hex)
                fr24_queried.add(hex)
                if fr24aircraft:
                    inserted = bs_db.insert_aircraft(fr24aircraft)
                    print("%s  - inserted=%s" % (fr24aircraft,inserted))        


    def read_csv():
        for plane in Tabular.parse_csv(rdataFolder + r'\\Mil.csv'):
            aircraft = bs_db.query_aircraft(plane.modes_hex)
            if aircraft:
                if not aircraft.is_complete():
                    bs_db.update_aircraft(plane)
                    print("%s updated" % plane.reg)
                else:
                    print(plane)
                    print(aircraft)
                    print("\n")
            else:
                bs_db.insert_aircraft(plane)
                print("%s inserted" % plane.reg)


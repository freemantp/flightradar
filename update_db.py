from adsb.flightradar24 import Flightradar24
from adsb.modesmixer import ModeSMixer
from adsb.basestationdb import BaseStationDB
from adsb.tabular import Tabular
import time
import signal
import sys
import json

with open('config.json', 'r') as jf:
    config = json.load(jf)
    dataFolder = config['dataFolder']
    host = config['host']
    port = config['port']

bs_db = BaseStationDB(dataFolder + "BaseStation.sqb")

fr24_queried = set()
not_found = set()

def signal_handler(signal, frame):
        print('You pressed Ctrl+C!')
        for hex in not_found:
            print(hex)

        sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

def is_swiss(icaohex):
    if icaohex and icaohex[0:2] == "4B":
        third = int(icaohex[2],16)
        if third >=0 and third <=8:
            return True
    return False

def update_live_from_fr24():

    fr24 = Flightradar24()
    msm = ModeSMixer(host, port)

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
                        print("%s  - updated=%s" % (aircraft,updated))
                    else:
                        not_found.add(hex)

            if not aircraft:
                fr24aircraft = fr24.query_aircraft(hex)
                fr24_queried.add(hex)
                if fr24aircraft:
                    inserted = bs_db.insert_aircraft(fr24aircraft)
                    print("%s  - inserted=%s" % (fr24aircraft,inserted))

        print("sleeping")
        time.sleep(20)

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

update_live_from_fr24()

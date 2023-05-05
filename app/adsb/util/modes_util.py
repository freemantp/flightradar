import time
import datetime
import csv
import string
from os import path

from ...config import Config

from ..db.basestationdb import BaseStationDB
from ..datasource.modesmixer import ModeSMixer

class ModesUtil:

    def __init__(self, folder):

        self.ranges = []

        file_name = path.join(folder, 'mil_ranges.csv')

        with open(file_name, newline='') as csvfile:
            rreader = csv.reader(csvfile, delimiter=';', quotechar='|')
            for row in rreader:
                newrange = (int(row[0]), int(row[1]))
                self.ranges.append(newrange)

            csvfile.close()
    
    @staticmethod
    def is_icao24_addr(icao24: str):
        return len(icao24) == 6 and all(c in string.hexdigits for c in icao24)

    def is_military(self, icao24):

        """ Returns true if the icao code military range """
        icao_nr = int(icao24, 16)

        for a_range in self.ranges:
            if a_range[0] == (icao_nr & a_range[1]):
                return True
        return False

    @staticmethod
    def is_swiss_mil(icao):

        """ Returns true if the icao code is in the Swiss military range """
        return icao >= 0x4B7000 and icao <= 0x4B7FFF

    @staticmethod
    def is_swiss(icaohex: str):
        if icaohex and icaohex[0:2] == "4B":
            third = int(icaohex[2], 16)
            if third >= 0 and third <= 8:
                return True
        return False


if __name__ == "__main__":

    app_cfg = Config()
    app_cfg.from_file('config.json')

    mil_ranges = ModesUtil(app_cfg.data_folder)

    bs_db = BaseStationDB(file_name = path.join(app_cfg.data_folder, 'BaseStation.sqb'))
    found_mil_ac = set()

    def handle_ac(icao24):
        if icao24 not in found_mil_ac:
            if mil_ranges.is_military(icao24):
                aircraft = bs_db.query_aircraft(icao24)

                datestring = datetime.datetime.now().strftime("%m.%d.%Y, %H:%M:%S")

                if aircraft:
                    aircraft_string = str(aircraft)
                else:
                    aircraft_string = icao24

                print("[%s] %s" % (datestring, aircraft_string) )

                found_mil_ac.add(icao24)

    def run_live():
        while True:
            msm = ModeSMixer(app_cfg.service_url)

            for line in msm.query_live_icao24():
                handle_ac(line.strip())

            time.sleep(10)

    run_live()

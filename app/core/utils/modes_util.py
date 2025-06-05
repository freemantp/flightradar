import csv
import string
from os import path

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
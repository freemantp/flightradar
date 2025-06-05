import csv
from ..aircraft import Aircraft

class Tabular:

    """ Parse tabular data from files """

    @staticmethod
    def parse_csv(file):

        planes = []

        with open(file, newline='') as csvfile:
            airreader = csv.reader(csvfile, delimiter=';', quotechar='|')

            for row in airreader:
                planes.append(Aircraft(row[0], row[1], row[3], row[2], row[4]))

        return planes


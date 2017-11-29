import json
import time

import threading

from flask import Flask
from flask import Response

from adsb.config import Config
from adsb.basestationdb import BaseStationDB
from adsb.modesmixer import ModeSMixer
from adsb.military import MilRanges


app = Flask(__name__)

adsb_config = Config('config.json')
bs_db = BaseStationDB(adsb_config.data_folder + "BaseStation.sqb")

class UpdaterThread(threading.Thread):

    def __init__(self, config):

        threading.Thread.__init__(self)
        self.mm2 = ModeSMixer(config.host, config.port)
        self.mil_ranges = MilRanges(config.data_folder)
        self.interrupted = False

    def run(self):

        while not self.interrupted:
            print("hello from thread %s, " % threading.get_ident())
            time.sleep(2)

        print("interupted")

t = UpdaterThread(adsb_config)
t.start()
#print(threading.get_ident())

@app.route("/")
def hello():


    t.interrupted = True

    response = []

    #for icao24 in mm2.query_live_aircraft():

     #   aircraft = bs_db.query_aircraft(icao24)

     #   response.append(str(aircraft))

    print(response)
    return Response(json.dumps(response), mimetype='application/json')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)

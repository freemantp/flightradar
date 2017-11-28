import json

from flask import Flask
from flask import Response

from adsb.config import Config
from adsb.basestationdb import BaseStationDB
from adsb.modesmixer import ModeSMixer
from adsb.military import MilRanges


app = Flask(__name__)

adsb_config = Config('config.json')
bs_db = BaseStationDB(adsb_config.data_folder + "BaseStation.sqb")
mm2 = ModeSMixer(adsb_config.host, adsb_config.port)
mil_ranges = MilRanges(adsb_config.data_folder)

@app.route("/")
def hello():

    response = []

    for icao24 in mm2.query_live_aircraft():

        aircraft = bs_db.query_aircraft(icao24)

        response.append(str(aircraft))

    print(response)
    return Response(json.dumps(response), mimetype='application/json')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)

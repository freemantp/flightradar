import json, time

from flask import Flask
from flask import Response
from flask import render_template
from flask import jsonify

from adsb.config import Config
from adsb.basestationdb import BaseStationDB

from updateThread import UpdaterThread

app = Flask(__name__)

adsb_config = Config('config.json')
bs_db = BaseStationDB(adsb_config.data_folder + "BaseStation.sqb")        

updater = UpdaterThread(adsb_config)
updater.start()

@app.route("/api")
def rest_api():
    response = []

    for icao24, tmstmp in updater.aircraft.items():
        aircraft = bs_db.query_aircraft(icao24)

        if aircraft:
            response.append((aircraft.__dict__, time.ctime(tmstmp)))


    return Response(json.dumps(response), mimetype='application/json')

@app.route("/")
def index():

    response = []

    for icao24, tmstmp in updater.aircraft.items():
        aircraft = bs_db.query_aircraft(icao24)

        if aircraft:
            response.append((aircraft.__dict__, time.ctime(tmstmp)))
    
    return render_template('aircraft.html', airplanes=response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)

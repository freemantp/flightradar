import json

from . import api
from .. import get_basestation_db
from ..adsb.db.dbrepository import DBRepository

from flask import current_app as app, Response

@api.route("/pos/<flight_id>") 
def get_positions(flight_id):

    if flight_id:

        try:
            int(flight_id)

            positions = DBRepository.get_positions(flight_id)

            if positions:
                pos_entries = [[ [p.lat, p.lon, p.alt] for p in positions]]
                return Response(json.dumps(pos_entries), mimetype='application/json')

        except ValueError:
            return "Invalid flight id format", 400
        except:
            return 500
    
    return 'Not found', 404

@api.route('/test')
def test_route():

    print(app.config['data_folder'])

    return "test"   

@api.route('/base')
def test_route2():

    baseSt = get_basestation_db()

    print(baseSt)

    return "go"   
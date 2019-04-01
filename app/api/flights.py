from . import api
from flask import current_app as app
from .. import get_basestation_db

@api.route('/test')
def test_route():

    print(app.config['data_folder'])

    return "test"   

@api.route('/base')
def test_route2():

    baseSt = get_basestation_db()

    print(baseSt)

    return "go"   
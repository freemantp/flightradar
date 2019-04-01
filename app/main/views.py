from . import main
from flask import render_template, current_app as app
from .. import get_basestation_db

from .. adsb.aircraft import Aircraft
from .. adsb.db.dbmodels import Flight
from .. adsb.flightupdater import FlightUpdater

from .. import get_basestation_db

import time
from pytz import timezone
from dateutil import tz

@main.route('/')
def index():

    if app.config['delete_after'] > 0:

        result_set = (Flight.select(Flight.id, Flight.callsign, Flight.modeS, Flight.archived, Flight.last_contact)
                            .order_by(Flight.last_contact.desc()))
    else:
        result_set = (Flight.select(Flight.id, Flight.callsign, Flight.modeS, Flight.archived, Flight.last_contact)
                            .order_by(Flight.last_contact.desc()))

    return render_flights(result_set)

def render_flights(flights, archived = False):

    response = []

    for flight in flights:

        aircraft = get_basestation_db().query_aircraft(flight.modeS)
        
        if not aircraft:
            aircraft = Aircraft(flight.modeS)
        response.append((aircraft.__dict__, flight.last_contact, flight.archived, flight.callsign, flight.id))
            
    updater = FlightUpdater.Instance()

    metaInfo = {
        'updaterAlive' : updater.isAlive(),
        'serviceAlive' : updater.is_service_alive(),
        'mode' : 'ModeSmixer2' if app.config['type'] == 'mm2' else 'VirtualRadar',
        'archived' : archived
    }    

    return render_template('aircraft.html', airplanes=response, status=metaInfo, silhouette=updater.get_silhouete_params())
    
@main.app_template_filter()
def localdate(value, format="%d.%m.%Y %H:%M"):    
    utctime = timezone('UTC').localize(value)
    local_time = utctime.astimezone(tz.gettz('Europe/Zurich'))
    return local_time.strftime(format)
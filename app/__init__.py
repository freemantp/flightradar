from flask import Flask, Blueprint, g
from click import get_current_context
from os import path

from .config import Config
from .meta import MetaInformation
from .adsb.db.basestationdb import BaseStationDB
from .adsb.db.dbmodels import init_db
from .adsb.util.logging import init_logging
from .util.encoder import RadarJsonEncoder
from .adsb.util.modes_util import ModesUtil

from .scheduling import configure_scheduling

def get_basestation_db():
    from flask import current_app as app

    basestation_db = getattr(g, '_basestation_db', None)
    if basestation_db is None:
        basestation_db = g._basestation_db = BaseStationDB(path.join(app.config['DATA_FOLDER'], 'BaseStation.sqb'))
    return basestation_db

def create_app():
    app = Flask(__name__)

    # TODO: make configurable
    if True:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app)

    # Config
    conf = Config() 
    app.config.from_object(conf)
    init_logging(conf.LOGGING_CONFIG)

    app.metaInfo = MetaInformation()
    app.flight_db = init_db(conf.DATA_FOLDER)
    app.modes_util = ModesUtil(conf.DATA_FOLDER)

    app.json_encoder = RadarJsonEncoder

    from .api import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api/v1')

    # Run asynchronous tasks only if in run mode
    click_ctx = get_current_context(True)
    if not click_ctx or (click_ctx and click_ctx.info_name == 'run'):
        configure_scheduling(app, conf)

    return app


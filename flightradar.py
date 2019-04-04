from app import create_app

from app.adsb.config import Config
from app import create_updater
from app.adsb.db.dbmodels import init_db_schema

import atexit

if __name__ == '__main__':

    conf = Config()
    conf.from_file('config.json')

    flight_db = init_db_schema(conf.data_folder)
    updater = create_updater(conf, flight_db)
    updater.start()

    app = create_app(conf)
    app.updater = updater
    app.run(host='0.0.0.0', debug=False)


@atexit.register
def _stop_worker_threads():
    flight_db.stop()
    updater.stop()
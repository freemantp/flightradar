from app import create_app
from app.config import Config
from app import create_updater
from app.adsb.db.dbmodels import init_db_schema, Flight, Position

import atexit

conf = Config()

app = create_app()
app.config.from_object(conf)

# TODO: Really do this on startup??
flight_db = init_db_schema(conf.DATA_FOLDER)

updater = create_updater(conf)
app.updater = updater
updater.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)

@app.shell_context_processor
def make_shel_context():
    return dict(db=flight_db, Flight=Flight, Position=Position)

@atexit.register
def _stop_worker_threads():
    flight_db.stop()
    updater.stop()
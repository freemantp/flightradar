from click import get_current_context
from .app import create_app

app, flight_db = create_app()

# Run asynchronous tasks if not in shell mode
if get_current_context().info_name != 'shell':
    app.apscheduler.start()

@app.shell_context_processor
def make_shel_context():
    from .app.adsb.db.dbmodels import Flight, Position
    from .app.adsb.db.dbrepository import DBRepository
    return dict(db=flight_db, Flight=Flight, Position=Position, DBRepository=DBRepository)

from app import create_app
from app.adsb.db.dbmodels import init_db_schema, Flight, Position

app = create_app()

@app.shell_context_processor
def make_shel_context():
    return dict(db=flight_db, Flight=Flight, Position=Position)

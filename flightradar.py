from .app import create_app

app = create_app()

@app.shell_context_processor
def make_shel_context():
    from .app.adsb.db.dbmodels import Flight, Position
    from .app.adsb.db.dbrepository import DBRepository
    return dict(db=app.flight_db, Flight=Flight, Position=Position, DBRepository=DBRepository)

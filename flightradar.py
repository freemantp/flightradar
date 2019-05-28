from app import create_app

app = create_app()

@app.cli.command('init-schema')
def init_db_schema():
    """Initialize DB schema."""

    from .app.adsb.db.dbmodels import init_schema, init_db
    from .app.config import Config

    conf = Config() 
    db = init_db(conf.DATA_FOLDER)
    init_schema(db)

@app.shell_context_processor
def make_shel_context():

    from .app.adsb.db.dbmodels import Flight, Position
    from .app.adsb.db.dbrepository import DBRepository
    return dict(db=app.flight_db, Flight=Flight, Position=Position, DBRepository=DBRepository)
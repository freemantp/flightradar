from fastapi import FastAPI, Depends
import typer

from app import create_app

app = create_app()

cli = typer.Typer()


@cli.command()
def initschema():
    """Initialize DB schema."""

    from app.adsb.db.dbmodels import init_schema, init_db
    from app.config import Config

    conf = Config()
    db = init_db(conf.DATA_FOLDER)
    init_schema(db)
    print("Database schema initialized successfully")


@cli.command()
def hello():
    print("Hello!")


if __name__ == "__main__":
    cli()

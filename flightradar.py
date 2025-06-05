from fastapi import FastAPI, Depends
import typer

from app import create_app

app = create_app()

cli = typer.Typer()


@cli.command()
def initschema():
    """Initialize MongoDB schema."""

    from app.data import init_mongodb
    from app.config import Config

    conf = Config()
    mongodb = init_mongodb(conf.MONGODB_URI, conf.MONGODB_DB_NAME, conf.DB_RETENTION_MIN)
    print("MongoDB database initialized successfully")


@cli.command()
def hello():
    print("Hello!")


if __name__ == "__main__":
    cli()

from flask import Flask
from .util.json_provider import RadarJsonProvider

class RadarFlask(Flask):
    json_provider_class = RadarJsonProvider
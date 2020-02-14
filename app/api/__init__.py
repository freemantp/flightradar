from flask import Blueprint

api = Blueprint('api', __name__)

from . import flights
from . import aircraft


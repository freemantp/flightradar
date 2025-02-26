from fastapi import APIRouter

router = APIRouter()

from . import flights
from . import aircraft


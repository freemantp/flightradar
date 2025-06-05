from fastapi import APIRouter

router = APIRouter()

from .endpoints import flights
from .endpoints import aircraft


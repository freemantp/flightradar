#!/bin/sh
exec venv/bin/uvicorn flightradar:app --host 0.0.0.0 --port 8083
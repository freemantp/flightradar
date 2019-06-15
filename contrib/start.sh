#!/bin/sh
exec venv/bin/gunicorn flightradar:app --bind 0.0.0.0:5000
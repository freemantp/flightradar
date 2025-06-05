#!/bin/sh
exec uv run uvicorn flightradar:app --host 0.0.0.0 --port 8083
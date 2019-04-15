#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
#PYTHONPATH="$(dirname $SCRIPT_DIR)"
PYTHONPATH=$SCRIPT_DIR

FLASK_APP=flightradar.py

cd $PYTHONPATH
venv/bin/python -m flask run

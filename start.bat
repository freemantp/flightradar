@echo off
SET PYTHONPATH=%~dp0
cd %PYTHONPATH%
SET FLASK_APP=flightradar.py
venv\Scripts\python -m flask run
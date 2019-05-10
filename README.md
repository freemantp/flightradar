# Flight radar view

Polls flight data from radar servers (ModeSMixer2 or VirtualRadarServer) and presents a chronological view of past flights with an interative live map of position reports. 

## Prerequisites

1. Make sure you have Python 3 installed, on Raspbian check with
```python3 --version```
1. Install the python flask package with ```pip3 install -r requirements.txt```

## Configuration

The application can either be configured by enviroment variables or by a config file

### Config file

1. Copy the ```config.json``` from contrib/samples to the project root
2. Configure host/port of your radar server
3. Set the path to your data folder. It must contain BaseStation.sqb (not included) and mil_ranges.csv, Example ``` "dataFolder" : "/home/pi/adsb-playground/resources/",```
4. Chose whether you want to see military planes only

### Enviroment variables

See section below for details

* DATA_FOLDER
* SERVICE_URL
* SERVICE_TYPE
* MIL_ONLY
* DB_RETENTION_MIN

### Config options

* ```serviceUrl``` The url to your radar service
* ```type``` The type of your radar service, eithr vrs for VirtualRadarServer or mm2 for ModeSMixer2  
* ```dataFolder``` the absolute path to your resources folder
* ```militaryOnly``` Whether everything other than military planes should be filtered (true or false)
* ```dbRetentionMinutes``` Determines how many minutes after the last signal was received should the the flight in the dababase be retained before it's deleted. Set to 0 to keep entries indefinitely
* ```logging``` [optional] This section allows to configure logging.
    * ```syslogHost``` The host to send logs to 
    * ```syslogFormat``` The syslog log format
    * ```logLevel``` [optional] Log level, See https://docs.python.org/2/library/logging.html#logging-levels
    * ```logToConsole``` [optional] If true, logs are logged to syslog and to console, if false only to syslog

## Running



```
SET FLASK_APP=flightradar.py
flask run
```



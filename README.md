# Flight radar

Fetches [ADS-B](https://en.wikipedia.org/wiki/Automatic_dependent_surveillance_-_broadcast) flight data from radar servers ([ModeSMixer2](http://xdeco.org/?page_id=48) or [Virtual Radar Server](http://www.virtualradarserver.co.uk/)) and presents a chronological view of past flights with an interactive live map of position reports. Built with FastAPI 

## Impressions

### Ovierview of past flights
![Aircraft](https://user-images.githubusercontent.com/54601848/71522312-70d61200-28c4-11ea-9295-cd98c9d20b42.png)

### Flight path visualization
![Flightpath](https://user-images.githubusercontent.com/54601848/71522306-6ae03100-28c4-11ea-9db8-c93fad289ffe.png)

## Prerequisites

1. Make sure you have Python 3 installed,
1. Install the dependencies package with ```pip3 install -r requirements.txt```

## Configuration

The application can either be configured by enviroment variables or by a config file

### Config file

1. Copy the ```config.json``` from contrib/samples to the project root
2. Configure host/port of your radar server
3. Set the path to your data folder. It must contain BaseStation.sqb (not included, [get it here](https://data.flightairmap.com/)) and mil_ranges.csv. Example ``` "dataFolder" : "/path/to/installation/resources/",```
4. Chose whether you want to track military planes only

### Enviroment variables

See section below for details

* DATA_FOLDER
* SERVICE_URL
* SERVICE_TYPE
* MIL_ONLY
* DB_RETENTION_MIN
* UNKNOWN_AIRCRAFT_CRAWLING

### Config options

| Option name                | Optional | Default value | Description                                                                                                                                                                                                                                                                                                                        |
|----------------------------|----------|---------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ```serviceUrl```           | no       |               | The url to your radar service                                                                                                                                                                                                                                                                                                      |
| ```type```                 | yes      | vrs           | The type of your radar service, eithr vrs for VirtualRadarServer, mm2 for ModeSMixer2 or dmp1090 for dump1090                                                                                                                                                                                                                                           |
| ```dataFolder```           | yes      | resources     | the absolute path to your resources folder                                                                                                                                                                                                                                                                                         |
| ```militaryOnly```         | yes      | false         | Whether everything other than military planes should be filtered (true or false)                                                                                                                                                                                                                                                   |
| ```deleteAfterMinutes```   | yes      | 1440          | Determines how many minutes after the last signal was received should the the flight in the dababase be retained before it's deleted. Set to 0 to keep entries indefinitely                                                                                                                                                        |
| ```logging```              | yes      |               | ```syslogHost``` The host to send logs to<br>```syslogFormat``` The syslog log format<br>```logLevel``` [optional] Log level, See [here](https://docs.python.org/2/library/logging.html#logging-levels) for more infos<br>```logToConsole``` [optional] If true, logs are logged to syslog and to console, if false only to syslog |
| ```crawlUnknownAircraft``` | yes      | false         | If true, aircraft not found in BaseStation.sqb will be looked up in various data sources in the web. Since this method uses crawling which might now always be allowed. Beware: This could potentially lead to blockage of your IP address                                                                                         |
| ```googleMapsApiKey```     | no       |               | The map view needs an API key to render the map. You can get one [here](https://developers.google.com/maps/documentation/javascript/get-api-key).                           

## Running Flightradar

### Initializing the database

flightradar uses an Sqlite3 database (resources/flights.sqlite) to store flight information. You have to create and initialize the database with its schema first. When building a docker image, the database is initialized upon build time. 

Initialize schema:
```
python flightradar.py initschema
```

### Starting the application

Running it with the development server (__Not recommended__ for productive use). Don't forget to initialize the db (see above) before the first run:

```
uvicorn flightradar:app --reload
```

Running it with ASGI in production (__recommended setup__) (binds to all interfaces on port 8083):
```
uvicorn flightradar:app --host 0.0.0.0 --port 8083
```

Or using Gunicorn with Uvicorn workers:
```
gunicorn flightradar:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8083
```

## Using Windows
When running the application on Windows, consider the following: 
* Use ```SET``` instead of ```export``` when using Windows

## Known issues
* Performance may suffer if you have a lot of flights in your database. There's a lot of potential for improvement in the persistence layer.
* If you're running it in a Docker container, the flight db runs in the same container. Adding the possibility to externalize it might be a good idea 


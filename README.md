# Military planes view

## Prerequisites

1. Make sure you have Python 3 installed, on Raspbian check with
```python3 --version```
1. Install the python flask package with ```pip3 install flask```
1. Install the peewee package with ```pip3 install peewee```

## Configuration

1. Pick a config file: (mm2 for ModeSMixer2, vrs for VirtualRadarServer) and rename it to ```config.json```
2. Configure host/port of either your ModeSMixer2 or VirtualRadarServer instance
3. Set the path to your data folder. It must contain BaseStation.sqb (not included) and mil_ranges.csv, Example ``` "dataFolder" : "/home/pi/adsb-playground/resources/",```
4. Chose whether you want to see military planes only

## Running

```python3 web.py```
class PositionReport:
    def __init__(self, icao24, lat, lon, alt, track, callsign):
        self.icao24 = icao24
        self.lat = lat
        self.lon = lon
        self.alt = alt
        self.track = track
        self.callsign = callsign
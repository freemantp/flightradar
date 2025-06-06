""" Aircraft module """

class Aircraft:
    """ Aircraft data """

    def __init__(self, modeShex, reg=None, icao_type_code=None, aircraft_type_description=None, operator=None, source=None, icao_type_designator=None):

        if not modeShex:
            raise ValueError("Empty hex code not allowed")

        self.modes_hex = modeShex.strip()
        self.reg = reg.strip() if reg else None
        self.icao_type_code = icao_type_code.strip() if icao_type_code else None
        self.aircraft_type_description = aircraft_type_description.strip() if aircraft_type_description else None
        self.operator = operator.strip() if operator else None
        self.source = source.strip() if source else None
        self.icao_type_designator = icao_type_designator.strip() if icao_type_designator else None

    def merge(self, other_aircraft):

        changes = False

        if self.modes_hex == other_aircraft.modes_hex:
            if not self.reg and other_aircraft.reg:
                self.reg = other_aircraft.reg
                changes = True
            if not self.icao_type_code and other_aircraft.icao_type_code:
                self.icao_type_code = other_aircraft.icao_type_code
                changes = True
            if not self.aircraft_type_description and other_aircraft.aircraft_type_description:
                self.aircraft_type_description = other_aircraft.aircraft_type_description
                changes = True
            if not self.operator and other_aircraft.operator:
                self.operator = other_aircraft.operator
                changes = True
            if not self.source and other_aircraft.source:
                self.source = other_aircraft.source
                changes = True
            if not self.icao_type_designator and other_aircraft.icao_type_designator:
                self.icao_type_designator = other_aircraft.icao_type_designator
                changes = True
            return changes
        else:
            return False

    def has_type(self):
        return not self.icao_type_code is None and not self.aircraft_type_description is None

    def is_complete(self):
        return self.has_type() and not (self.reg is None)
    
    def is_complete_with_operator(self):
        return self.is_complete() and not (self.operator is None)

    def is_empty(self):
        return not self.reg and not self.icao_type_code and not self.aircraft_type_description and not self.operator and not self.icao_type_designator

    def __str__(self):
        return "mode-s:%s, reg:%s, icao:%s, type:%s, op:%s" % (self.modes_hex, self.reg, self.icao_type_code, self.aircraft_type_description, self.operator)

""" Aircraft module """

class Aircraft:
    """ Aircraft data """

    def __init__(self, modeShex, reg=None, type1=None, type2=None, operator=None):

        if not modeShex:
            raise ValueError("Empty hex code not allowed")

        self.modes_hex = modeShex.strip()
        self.reg = reg.strip() if reg else None
        self.type1 = type1.strip() if type1 else None
        self.type2 = type2.strip() if type2 else None
        self.operator = operator.strip() if operator else None

    def merge(self, other_aircraft):

        changes = False

        if self.modes_hex == other_aircraft.modes_hex:
            if not self.reg and other_aircraft.reg:
                self.reg = other_aircraft.reg
                changes = True
            if not self.type1 and other_aircraft.type1:
                self.type1 = other_aircraft.type1
                changes = True
            if not self.type2 and other_aircraft.type2:
                self.type2 = other_aircraft.type2
                changes = True
            if not self.operator and other_aircraft.operator:
                self.operator = other_aircraft.operator
                changes = True
            return changes
        else:
            return False

    def has_type(self):
        return not self.type1 is None and not self.type2 is None

    def is_complete(self):
        return self.has_type() and not (self.reg is None)

    def is_complete2(self):
        return self.is_complete() and not (self.operator is None)

    def __str__(self):
        return "hex:%s, reg:%s, icao:%s, type:%s, op:%s" % (self.modes_hex, self.reg, self.type1, self.type2, self.operator)

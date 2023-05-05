from flask.json.provider import JSONProvider
from decimal import Decimal
import orjson

class RadarJsonProvider(JSONProvider):

    def dumps(self, obj, *, option=None, **kwargs):

        if option is None:
            option = orjson.OPT_APPEND_NEWLINE | orjson.OPT_NAIVE_UTC

  
        return orjson.dumps(obj, option=option).decode()

    def loads(self, s, **kwargs):
        return orjson.loads(s)

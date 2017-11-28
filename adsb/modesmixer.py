from http.client import HTTPConnection
import json
from base64 import b64encode

from .aircraft import Aircraft

class ModeSMixer:

    """ ModeSMixer Queries """

    def __init__(self, host, port):

        self.host = host
        self.port = port

        self.headers = { 
            'Authorization' : 'Basic %s' %  b64encode(b"user:pwdhere").decode("ascii"),
            "Content-type": "application/json", "Accept": "*/*"
        }
        self.body = """{"req":"getStats","data":{"statsType":"flights","id":0}}"""     

    def query_live_aircraft(self):

        conn = HTTPConnection(self. host,self.port)
        conn.request('POST', '/json', body=self.body, headers=self.headers)

        #get the response back
        res = conn.getresponse()
        # at this point you could check the status etc
        # this gets the page text
        data = res.read()  

        json_obj = json.loads(data.decode())

        flights = json_obj['stats']['flights']

        hexcodes = []

        for fl in flights:
            icaohex = str(fl['I'])
            hexcodes.append(icaohex)


        conn.close()
        return hexcodes

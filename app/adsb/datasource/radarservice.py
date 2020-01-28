from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urlparse
from base64 import b64encode

class RadarService:

    def __init__(self, url):
        
        self._url_parms = urlparse(url)

        self.base_path = '{:s}://{:s}{:s}'.format(
            self._url_parms.scheme, 
            self._url_parms.netloc, 
            self._url_parms.path)
            
        self.headers = {
            'Accept' : 'application/json'
        }

        if self._url_parms.username and self._url_parms.password:
            basicAuth = '{:s}:{:s}'.format(self._url_parms.username, self._url_parms.password).encode('utf-8')
            self.headers['Authorization'] = 'Basic {:s}'.format(b64encode(basicAuth).decode("ascii"))

        self.connection_alive = True

    #deprecated
    def get_connection(self):
        if self._url_parms.scheme == 'http':
            return HTTPConnection(self._url_parms.hostname,self._url_parms.port)
        elif self._url_parms.scheme == 'https':
            return HTTPSConnection(self._url_parms.hostname,self._url_parms.port)
        else:
            raise ValueError('Invalid protocol in service url')

    @staticmethod
    def _urljoin(*args):
        """
        Joins given arguments into an url. Trailing but not leading slashes are
        stripped for each argument.
        """

        return "/".join(map(lambda x: str(x).rstrip('/'), args))            

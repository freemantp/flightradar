import json

class Config():

    """ Application configuration """

    def __init__(self):
        self.data_folder = ''
        self.service_url = ''
        self.military_only = False
        self.type = 'mm2'

    def from_file(self, filename):
        with open(filename, 'r') as json_file:
            config = json.load(json_file)
            url = config['serviceUrl']
            self.data_folder = config['dataFolder']
            self.service_url = url[:-1] if url[-1] == "/" else url
            self.type = config['type']
            self.military_only = config['militaryOnly']
    
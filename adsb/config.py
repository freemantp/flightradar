import json

class Config():

    """ Application configuration """

    def __init__(self):
        self.data_folder = ''
        self.service_host_name = ''
        self.service_port = ''
        self.military_only = False
        self.type = 'mm2'

    def from_file(self, filename):
        with open(filename, 'r') as json_file:
            config = json.load(json_file)
            self.data_folder = config['dataFolder']
            self.service_host_name = config['serviceHostName']
            self.service_port = config['servicePort']
            self.type = config['type']
            self.military_only = config['militaryOnly']
    
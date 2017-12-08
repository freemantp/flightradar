import json

class Config():

    """ Application configuration """

    def __init__(self):
        self.data_folder = ''
        self.host = ''
        self.port = ''

    def from_file(self, filename):
        with open(filename, 'r') as json_file:
            config = json.load(json_file)
            self.data_folder = config['dataFolder']
            self.host = config['host']
            self.port = config['port']
    
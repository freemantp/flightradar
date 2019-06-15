import json
import os
import logging
from pathlib import Path

class MetaInformation:

    """ Application configuration """

    COMMIT_ID = None
    BUILD_TIMESTAMP = None

    def __init__(self):

        FILE_PATH = 'resources/meta.json'

        config_file = Path(FILE_PATH)
        if config_file.is_file():
            self.from_file(FILE_PATH)

    def from_file(self, filename):
        with open(filename, 'r') as json_file:
            config = json.load(json_file)

            if 'gitCommitId' in config:
                self.COMMIT_ID = config['gitCommitId']

            if 'buildTimestamp' in config:
                self.BUILD_TIMESTAMP = config['buildTimestamp']
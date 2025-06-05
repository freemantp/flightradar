import json
from pathlib import Path

class MetaInformation:

    """ Application configuration """

    commit_id = None
    build_timestamp = None

    def __init__(self):

        FILE_PATH = 'resources/meta.json'

        config_file = Path(FILE_PATH)
        if config_file.is_file():
            self.from_file(FILE_PATH)

    def from_file(self, filename):
        with open(filename, 'r') as json_file:
            config = json.load(json_file)

            # Support both camelCase and snake_case for backwards compatibility
            if 'commit_id' in config:
                self.commit_id = config['commit_id']
            elif 'gitCommitId' in config:
                self.commit_id = config['gitCommitId']

            if 'build_timestamp' in config:
                self.build_timestamp = config['build_timestamp']
            elif 'buildTimestamp' in config:
                self.build_timestamp = config['buildTimestamp']
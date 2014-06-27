import inspect
import os
import json
from gaia.webservice.WebserviceError import WebserviceError


class Settings(object):
    def __init__(self):
        config_path = self.get_storage_path()

        if not os.path.isfile(config_path) or not os.access(config_path, os.R_OK):
            raise WebserviceError("Config file not readable or not found.")

        self._config = dict()
        self._file = open(config_path, "r+")

        self.read()

        for key in ("url", "username", "password"):
            if not key in self._config:
                raise WebserviceError("Missing required option %s." % key)

    @staticmethod
    def get_storage_path():
        """Get the location for the settings file"""

        path = os.path.realpath(inspect.getfile(inspect.currentframe()) + "/../../../")
        return path + "/settings.json"

    def write(self):
        """Write the settings to disk"""

        self._file.seek(0)
        self._file.truncate()

        json.dump(self._config, self._file, indent=True)

    def read(self):
        """Read the settings from disk"""

        try:
            self._config = json.load(self._file)

        except ValueError:
            self._config = {}

    def get(self, key):
        """Get a specific setting"""

        try:
            return self._config[key]

        except KeyError:
            return None

    def set(self, key, value):
        """Set a specific setting"""

        self._config[key] = value

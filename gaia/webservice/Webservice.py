import requests
import json
from gaia.webservice.WebserviceError import WebserviceError


class Webservice(object):
    def __init__(self, url, username=None, password=None):
        self.url = url
        self.token = None
        self.username = username
        self.password = password

    def call(self, extension, procedure, parameters={}):
        """Call a remote procedure and automatically get a new token whenever required."""
        payload = self.call_raw(extension, procedure, parameters)

        if not payload["_success"] and payload["_status"] == "Invalid or no token supplied.":
            # Used token seems to be expired, get a new one and try again
            self.token = None
            self.login(self.username, self.password)
            return self.call_raw(extension, procedure, parameters)

        return payload

    def call_raw(self, extension, procedure, parameters={}):
        """Call a remote procedure"""
        url = self.url + extension + ":" + procedure

        if self.token is not None:
            url = url + "?token=" + self.token

        response = requests.post(url, data={"payload": json.dumps(parameters)})

        print("Request: %s" % json.dumps(parameters))

        try:
            payload = response.json()
            print("Response: %s" % payload)
        except ValueError:
            print(response.text)
            raise

        return payload

    def login(self, username, password):
        """Login to get a new token"""
        response = self.call_raw("Session", "login", {"username": username, "password": password})

        if response["_success"]:
            self.token = response["token"]
            return True

        else:
            raise WebserviceError(response["_status"])

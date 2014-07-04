#!/usr/bin/env python
from gaia.drivers.CharLCDPlate import CharLCDPlate
from gaia.packingtracker.common import AppState
from gaia.packingtracker.director import Director
from gaia.webservice.Settings import Settings
from gaia.webservice.Webservice import Webservice

if __name__ == "__main__":
    def on_exit(director):
        assert isinstance(director, Director)

        def signal_handler(signum, frame):
            print("Caught signal %d" % signum)
            director.add_event(AppState.EVENT_QUIT, signum)

        return signal_handler

    lcd = CharLCDPlate()
    lcd.begin(16, 2)

    settings = Settings()

    ws = Webservice(settings.get("url"))
    ws.token = settings.get("token")
    ws.username = settings.get("username")
    ws.password = settings.get("password")

    director = Director(ws, settings.get("terminal"), lcd)

    import signal
    signal.signal(signal.SIGTERM, on_exit(director))

    director.start()

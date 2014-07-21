#!/usr/bin/env python
from gaia.drivers.CharLCDPlate import CharLCDPlate
from gaia.packingtracker.common import AppState
from gaia.packingtracker.director import Director
from gaia.webservice.Settings import Settings
from gaia.websocket.Websocket import Websocket

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

    ws = Websocket((settings.get("server"), 7191))
    ws.token = settings.get("token")
    ws.username = settings.get("username")
    ws.password = settings.get("password")
    ws.connect()
    ws.auth()

    director = Director(ws, lcd)
    director.terminal = settings.get("terminal")
    director.machine = settings.get("machine")

    import signal
    signal.signal(signal.SIGTERM, on_exit(director))

    director.start()

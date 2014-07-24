from gaia.drivers.CharLCDPlate import CharLCDPlate
from Queue import Queue, Empty
from gaia.packingtracker.common import AppState
from time import sleep
from gaia.drivers.barcode_scanner import BarcodeScanner, NoDeviceFoundError
from threading import Thread
from gaia.websocket.Websocket import Websocket


class ButtonsThread(Thread):
    def __init__(self, app_state, lcd):
        assert isinstance(app_state, AppState)
        assert isinstance(lcd, CharLCDPlate)

        Thread.__init__(self, name="buttons_thread")
        self.app_state = app_state
        self.lcd = lcd

    def run(self):
        while self.app_state.is_active():
            button = self.lcd.read_buttons()

            if button is not None:
                self.app_state.put((self.app_state.EVENT_BUTTON, button))

            sleep(1 / 50)

        print("Quitting buttons thread")


class NetworkThread(Thread):
    def __init__(self, app_state, ws):
        assert isinstance(app_state, AppState)
        assert isinstance(ws, Websocket)

        Thread.__init__(self, name="network_thread")
        self.ws = ws
        self.app_state = app_state
        self.request_queue = Queue()
        self.pending_requests = dict()

    def call_async(self, callback, extension, procedure, parameters):
        print("Adding new network request to stack")
        self.request_queue.put((callback, extension, procedure, parameters))

    def run(self):
        while self.app_state.is_active():
            # Look if there are new calls to send
            try:
                callback, extension, procedure, parameters = self.request_queue.get(block=False)

                print("Sending new request")

                msgid = self.ws.call(extension, procedure, parameters)
                self.pending_requests[msgid] = callback

            except Empty:
                pass

            # Look if there are new responses
            res = self.ws.wait_response()

            if res:
                print("There!", res)
                code, payload, msgid = res

                if msgid is None:
                    if code == 12:
                        self.app_state.add_event(AppState.EVENT_WS_EVENT, payload)

                elif msgid in ("auth", "login"):
                    self.app_state.add_event(AppState.EVENT_AUTH, payload)

                else:
                    callback = self.pending_requests.pop(msgid)
                    self.app_state.add_event(AppState.EVENT_NETWORK, (callback, payload))

            sleep(0.1)

        print("Quitting network thread")


class ScannerThread(Thread):
    def __init__(self, app_state):
        assert isinstance(app_state, AppState)

        Thread.__init__(self, name="scanner_thread")
        self.app_state = app_state

        self.scanner = None

    def run(self):
        while self.app_state.is_active():
            if self.scanner is None:
                self.search_scanner()
            else:
                self.read_scanner()

        print("Quitting scanner thread")

    def read_scanner(self):
        try:
            barcode = self.scanner.read(self.app_state.quit_event)

            if barcode is not None:
                self.app_state.put((self.app_state.EVENT_BARCODE, barcode))

        except (NoDeviceFoundError, AttributeError):
            self.scanner = None

            # Inform the main thread that the barcode scanner was unplugged
            self.app_state.add_event(AppState.EVENT_DEVICE, AppState.DEVICE_OUT)

    def search_scanner(self):
        """ If the barcode scanner is unplugged, his will keep searching for a barcode scanner until it is found. """
        self.scanner = BarcodeScanner.get_scanner()

        if self.scanner is not None:
            self.app_state.add_event(AppState.EVENT_DEVICE, AppState.DEVICE_IN)

        else:
            sleep(1)


class TimerThread(Thread):
    def __init__(self, app_state):
        Thread.__init__(self, name="timer_thread")
        self.app_state = app_state

    def run(self):
        while self.app_state.is_active():
            self.app_state.add_event(AppState.EVENT_TICK)
            sleep(1)

        print("Quitting timer thread")

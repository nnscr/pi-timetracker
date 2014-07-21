import Queue
from threading import current_thread
from os import system
from time import sleep
from gaia.packingtracker.common import AppState, ANSI
from gaia.packingtracker import thread
from gaia.packingtracker.mode import SelectPacker


class Director(AppState):
    def __init__(self, webservice, lcd):
        AppState.__init__(self, lcd)

        self.webservice = webservice

        # Children threads
        self.network_thread = thread.NetworkThread(self, self.webservice)
        self.buttons_thread = thread.ButtonsThread(self, self.lcd)
        self.scanner_thread = thread.ScannerThread(self)
        self.timer_thread = thread.TimerThread(self)

        self.network_thread.daemon = True
        self.buttons_thread.daemon = True
        self.scanner_thread.daemon = True
        self.timer_thread.daemon = True

        # Current mode
        self.mode = None

    def switch_mode(self, new_mode):
        print("Switching mode from %s to %s." % (
            ANSI.color(ANSI.FG + ANSI.COL_YELLOW, type(self.mode).__name__),
            ANSI.color(ANSI.FG + ANSI.COL_GREEN, type(new_mode).__name__)
        ))

        self.stop_timer()
        self.mode = new_mode
        self.mode.draw()

    def start(self):
        # Start all children threads
        self.network_thread.start()
        self.buttons_thread.start()
        self.scanner_thread.start()
        self.timer_thread.start()

        # Begin with packer selection
        self.switch_mode(SelectPacker(self))

        while self.is_active():
            try:
                event, value = self.get(block=False)

                print("Event %s: %s" % (
                    ANSI.color(ANSI.FG + ANSI.COL_RED, event),
                    ANSI.color(ANSI.FG + ANSI.COL_GREEN, value))
                )

                if event == AppState.EVENT_FINISH:
                    # A mode has finished
                    new_mode = self.mode.finish(value)

                    if new_mode is not None:
                        self.switch_mode(new_mode)

                    continue

                if event == AppState.EVENT_REFRESH:
                    # A display refresh is requested
                    self.mode.draw()

                if event == AppState.EVENT_QUIT:
                    # Quit the program
                    self.stop()

                if event == AppState.EVENT_DEVICE:
                    # Barcode scanner plugged in our plugged out
                    self.has_scanner = True if value == AppState.DEVICE_IN else False

                if event == AppState.EVENT_NETWORK:
                    # A network response has arrived
                    callback, response = value

                    if callback is not None:
                        callback(response)

                if event == AppState.EVENT_AUTH:
                    success, user = value

                    if not success:
                        # Authentication failed, maybe the token has expired.
                        # Try to login with user credentials.

                        self.webservice.login()
                    else:
                        self.webservice.token = value[1]["token"]
                        self.webservice.subscribe("machine")

                if event == AppState.EVENT_WS_EVENT:
                    channel, ev, data = value

                    if channel == "machine" and ev == "broken" and data["machine_name"] == self.machine:
                        self.breakdown = True
                        self.mode.draw()

                    elif channel == "machine" and ev == "repaired" and data["machine_name"] == self.machine:
                        self.breakdown = False
                        self.mode.draw()

                # Inform the current mode about the event
                self.mode.handle_event(event, value)

            except Queue.Empty:
                sleep(1 / 50)

    def stop(self, exit_=True):
        self.lcd.clear()
        self.lcd.backlight(self.lcd.OFF)

        print("Quitting %s" % current_thread().name)

        self.shutdown()

        self.buttons_thread.join()
        self.network_thread.join()
        self.timer_thread.join()
        self.scanner_thread.join()

        self.lcd.clear()
        self.lcd.backlight(self.lcd.OFF)

        if exit_:
            exit()

    def call_ws_async(self, callback, extension, procedure, parameters):
        self.network_thread.call_async(callback, extension, procedure, parameters)

    def shutdown_system(self):
        self.stop(False)
        system("/sbin/shutdown -h now")

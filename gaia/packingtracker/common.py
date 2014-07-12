from Queue import Queue
from threading import Event


class ANSI():
    BG = 40
    FG = 30

    COL_BLACK = 0
    COL_RED = 1
    COL_GREEN = 2
    COL_YELLOW = 3
    COL_BLUE = 4
    COL_MAGENTA = 5
    COL_CYAN = 6
    COL_WHITE = 7

    def __init__(self):
        pass

    @staticmethod
    def color(col, text):
        return "\033[%dm%s\033[0m" % (col, text)


class AppState(Queue):
    EVENT_BARCODE = "EVENT_BARCODE"  # A barcode has been scanned
    EVENT_BUTTON = "EVENT_BUTTON"  # A button has been pressed
    EVENT_DEVICE = "EVENT_DEVICE"  # A barcode scanner has plugged in or out
    EVENT_QUIT = "EVENT_QUIT"  # We want to quit
    EVENT_NETWORK = "EVENT_NETWORK"  # A network response has arrived
    EVENT_FINISH = "EVENT_FINISH"  # A mode has finished
    EVENT_REFRESH = "EVENT_REFRESH"  # Redraw the displays

    DEVICE_OUT = "DEVICE_OUT"
    DEVICE_IN = "DEVICE_IN"

    def __init__(self, lcd):
        Queue.__init__(self)

        # The quit event is set if the child threads are prompted to exit
        self.quit_event = Event()

        # Is a barcode scanner connected?
        self.has_scanner = False
        self.breakdown = False

        # Info about current packer
        self.packer_id = None
        self.packer_name = None

        # Devices
        self.lcd = lcd

        # Timer event
        self.timer_event = Event()
        self.timer_running = False

        # Static values from configuration file
        self.terminal = None
        self.machine = None

    def start_timer(self):
        self.timer_running = True
        self.timer_event.set()

    def stop_timer(self):
        self.timer_event.clear()
        self.timer_running = False

    def wait_timer(self):
        self.timer_event.wait()

    def add_event(self, event, value=None):
        self.put((event, value))

    def is_active(self):
        return not self.is_quitting()

    def is_quitting(self):
        return self.quit_event.isSet()

    def wait_quit(self, timeout=None):
        return self.quit_event.wait(timeout)

    def shutdown(self):
        self.quit_event.set()
        self.start_timer()

    def set_packer(self, packer_id, packer_name):
        self.packer_id = packer_id
        self.packer_name = packer_name

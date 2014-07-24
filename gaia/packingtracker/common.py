from Queue import Queue
from threading import Event
from RPi import GPIO


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
    EVENT_TICK = "EVENT_TICK"  # Timer tick
    EVENT_AUTH = "EVENT_AUTH"  # Websocket authentication happened
    EVENT_WS_EVENT = "EVENT_WS_EVENT"  # Websocket event arrived

    DEVICE_OUT = "DEVICE_OUT"
    DEVICE_IN = "DEVICE_IN"

    LED_RED = 0
    LED_YLW = 1
    LED_GRN = 2

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

        # Static values from configuration file
        self.terminal = None
        self.machine = None

        # Current LED states for flashing
        self.leds = LEDManager(leds=(
            LED(11, PowerLEDBehaviour(self)),
            LED(13, MaintenanceLEDBehaviour(self)),
            LED(15, TrackingLEDBehaviour(self))
        ))

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

    def set_packer(self, packer_id, packer_name):
        self.packer_id = packer_id
        self.packer_name = packer_name

    def is_tracking(self):
        pass


class LED(object):
    OFF = 0
    ON = 1
    FLASH = 2

    current = False
    mode = OFF

    def __init__(self, pin, behaviour):
        self.pin = pin
        self.behaviour = behaviour

    def refresh(self):
        self.mode = self.behaviour.get_mode()

        if self.mode == self.FLASH:
            self.current = not self.current
        else:
            self.current = self.mode

        self._set_level(self.current)

    def _set_level(self, level):
        GPIO.output(self.pin, level)


class LEDManager(object):
    def __init__(self, leds):
        self.leds = leds

        # Init GPIO for status leds
        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)

        for led in self.leds:
            GPIO.setup(led.pin, GPIO.OUT)

    def refresh(self):
        for led in self.leds:
            led.refresh()


class LEDBehaviour(object):
    def __init__(self, app_state):
        self.app = app_state

    def get_mode(self):
        pass


class PowerLEDBehaviour(LEDBehaviour):
    def get_mode(self):
        return LED.ON


class MaintenanceLEDBehaviour(LEDBehaviour):
    def get_mode(self):
        if self.app.breakdown:
            return LED.ON
        else:
            return LED.OFF


class TrackingLEDBehaviour(LEDBehaviour):
    def get_mode(self):
        if self.app.is_tracking():
            if self.app.mode.is_paused:
                return LED.FLASH
            else:
                return LED.ON
        else:
            return LED.OFF

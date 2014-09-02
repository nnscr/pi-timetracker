from Queue import Queue
from threading import Event, _Event
from RPi import GPIO
from time import sleep


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

        # Main event loop
        self.loop = EventLoop(self.is_active)

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

        # Tracking?
        self.tracking = False
        self.tracking_paused = False

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
        self.loop.stop()

    def set_packer(self, packer_id, packer_name):
        self.packer_id = packer_id
        self.packer_name = packer_name


class EventLoop(object):
    class Item(object):
        def __init__(self, loop, interval, event=None, callback=None):
            assert event is not None or callback is not None

            self._loop = loop
            self._interval = interval
            self._event = event
            self._callback = callback

        def notify(self):
            if self._event is not None:
                self._event.notify()

            else:
                self._callback()

        def release(self):
            if self._event is not None:
                self._event.notify()

        @property
        def interval(self):
            return self._interval

        @property
        def event(self):
            return self._event

    class Event(object):
        def __init__(self, cond):
            self._event = Event()
            self._cond = cond

        def wait(self):
            self._event.wait()
            self._event.clear()

            return self._cond()

        def notify(self):
            self._event.set()

    def __init__(self, cond):
        self._freq = None
        self._reset = None
        self._clock = 0
        self._events = list()
        self._cond = cond

    def add(self, interval, callback=None):
        assert interval > 0

        if callback is None:
            event = self.Event(self._cond)
            item = self.Item(self, interval, event=event)

        else:
            item = self.Item(self, interval, callback=callback)

        self._events.append(item)
        self._calculate_clock()

        return item

    def remove(self, callback):
        self._events.remove(callback)
        self._calculate_clock()

    def run(self):
        if self._freq is None:
            raise RuntimeError("Frequency not set, did you forget to add an event?")

        while self._cond():
            self._clock += 1

            cur = self._clock * self._freq

            for ev in self._events:
                if cur % ev.interval == 0:
                    ev.notify()

            if cur == self._reset:
                self._clock = 0

            sleep(self._freq / 1000.0)

    def stop(self):
        for item in self._events:
            item.release()

    def _calculate_clock(self):
        def gcd(*numbers):
            """Return the greatest common divisor of the given integers"""
            from fractions import gcd as gcd_
            return reduce(gcd_, numbers)

        def lcm(*numbers):
            """Return lowest common multiple."""
            def lcm_(a, b):
                return (a * b) // gcd(a, b)

            return reduce(lcm_, numbers, 1)

        intervals = [c.interval for c in self._events]

        print ("Intervals:", intervals)

        self._freq = gcd(*intervals)
        self._reset = lcm(*intervals)

        print "Calculated frequency: %f, reset at %f (%f)" % (self._freq, self._reset, (self._reset / self._freq))


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

    def reset(self):
        self._set_level(self.behaviour.reset())


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

    def reset(self):
        for led in self.leds:
            led.reset()


class LEDBehaviour(object):
    def __init__(self, app_state):
        self.app = app_state

    def get_mode(self):
        pass

    def reset(self):
        pass


class PowerLEDBehaviour(LEDBehaviour):
    def get_mode(self):
        return LED.ON

    def reset(self):
        return LED.ON


class MaintenanceLEDBehaviour(LEDBehaviour):
    def get_mode(self):
        if self.app.breakdown:
            return LED.ON
        else:
            return LED.OFF

    def reset(self):
        return LED.OFF


class TrackingLEDBehaviour(LEDBehaviour):
    def get_mode(self):
        if self.app.tracking:
            if self.app.tracking_paused:
                return LED.FLASH
            else:
                return LED.ON
        else:
            return LED.OFF

    def reset(self):
        return LED.OFF

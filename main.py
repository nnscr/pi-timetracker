import atexit
from math import floor
from threading import Thread, Lock, Semaphore, Event
from time import time
from CharLCDPlate import NumberSelector, CharLCDPlate, Menu
from gaia.webservice.Webservice import Webservice
from gaia.webservice.Settings import Settings
from time import sleep
from barcode_scanner import BarcodeScanner, NoDeviceFoundError
from os import system
from show_ip_addr import get_ip_addr

# Threads:
#  Barcodescanner
#  Tastenabfrage Tastatur
#  Hauptthread


class PackingTimeTracker(object):
    MODE_SELECT_PACKER = "select_packer"
    MODE_WAIT_INVOICE = "wait_invoice"
    MODE_TRACKING = "resume_tracking"
    MODE_MENU = "show_menu"

    ERROR_MESSAGES = {
        "Order not found.": "Bestellung\nnicht gefunden",
        "Failed to get order.": "Abruf\nfehlgeschlagen",
    }

    EVENT_BARCODE = 1
    EVENT_BUTTON = 2
    EVENT_DEVICE = 3

    def __init__(self, settings, lcd):
        self.settings = settings
        self.lcd = lcd
        self.sel = NumberSelector(self.lcd)
        self.sel.callback = self.select_packer_callback
        self.menu = Menu(self.lcd)
        self.menu.callback = self.menu_callback
        self.scanner = BarcodeScanner.get_scanner()
        self.mode = self.MODE_SELECT_PACKER

        self.terminal_id = self.settings.get("terminal")

        self.ws = Webservice(self.settings.get("url"))
        self.ws.token = self.settings.get("token")
        self.ws.username = self.settings.get("username")
        self.ws.password = self.settings.get("password")

        self.scanner_thread = Thread(target=self.scanner_thread, name="scanner_thread")
        self.buttons_thread = Thread(target=self.buttons_thread, name="buttons_thread")
        self.timer_thread = Thread(target=self.timer_thread, name="timer_thread")
        self.scanner_thread.daemon = True
        self.buttons_thread.daemon = True
        self.timer_thread.daemon = True

        self.lock = Lock()
        self.semaphore = Semaphore()
        self.timer_event = Event()

        self.event_stack = list()

        # Tracking status variables
        self.packer_id = None
        self.invoice = None
        self.start_time = None
        self.order_info = None

        # Saved previous modes for special cases
        self.previous_mode_menu = None

    def scanner_thread(self):
        while True:
            try:
                barcode = self.scanner.read()

                self.add_event((self.EVENT_BARCODE, barcode))

            except (NoDeviceFoundError, AttributeError):
                self.scanner = None

                # Inform the main thread that the barcode scanner was unplugged
                self.add_event((self.EVENT_DEVICE, "plugged_out"))

                # Let this thread search for a barcode scanner
                self.search_scanner()

    def add_event(self, event):
        self.lock.acquire()
        self.event_stack.append(event)
        self.semaphore.release()
        self.lock.release()

    def search_scanner(self):
        """ Called from the scanner thread, this will keep searching for a barcode scanner until it is found. """
        self.scanner = None

        while self.scanner is None:
            sleep(1)
            self.scanner = BarcodeScanner.get_scanner()

        self.add_event((self.EVENT_DEVICE, "plugged_in"))

    def buttons_thread(self):
        while True:
            button = self.lcd.read_buttons()

            self.add_event((self.EVENT_BUTTON, button))

    def timer_thread(self):
        while self.timer_event.wait() or True:
            while self.mode == self.MODE_TRACKING and self.start_time is not None:
                string = self.format_time(time() - self.start_time)

                string = string + (" " * (16 - len(string) - len(self.invoice))) + self.invoice
                string += "\n" + self.order_info

                self.lcd.message(string)
                self.timer_event.clear()
                sleep(1)

    def start(self):
        self.scanner_thread.start()
        self.buttons_thread.start()
        self.timer_thread.start()

        while self.semaphore.acquire():
            self.lock.acquire()
            for event in self.event_stack:
                group, value = event

                print("Event %02d: %s" % (group, value))

                if group == self.EVENT_BARCODE:
                    self.barcode_entered(value)
                elif group == self.EVENT_BUTTON:
                    self.button_pressed(value)
                elif group == self.EVENT_DEVICE:
                    self.barcode_scanner_plugged(value)

                self.event_stack.remove(event)
            self.lock.release()

    def barcode_scanner_plugged(self, in_out):
        if self.mode not in (self.MODE_MENU, self.MODE_SELECT_PACKER):
            self.resume()

    def barcode_entered(self, barcode):
        if self.mode == self.MODE_SELECT_PACKER:
            self.select_packer_callback(barcode)

        elif self.mode == self.MODE_WAIT_INVOICE:
            self.invoice = self.parse_invoice_barcode(barcode)
            self.start_tracking()

        elif self.mode == self.MODE_TRACKING:
            self.end_tracking()

    def button_pressed(self, button):
        if self.mode == self.MODE_SELECT_PACKER:
            self.sel.on_button_press(button)

        elif self.mode == self.MODE_MENU:
            self.menu.button_pressed(button)

        else:
            self.show_menu()

    def show_menu(self):
        self.previous_mode_menu = self.mode
        self.mode = self.MODE_MENU

        self.menu.show([
            ("logout", "Abmelden"),
            ("abort", "Paket\nabbrechen"),
            ("quit", "Beenden"),
            ("restart", "Programm\nneustarten"),
            ("shutdown", "Herunterfahren"),
            ("show_ip", "IP-Adresse\nanzeigen"),
        ])

    def menu_callback(self, option):
        if option == "logout":
            self.logout_packer()
        elif option == "abort":
            self.wait_invoice()
        elif option == "quit":
            self.quit()
        elif option == "restart":
            self.quit(restart=True)
        elif option == "shutdown":
            self.shutdown()
        elif option == "show_ip":
            ip = get_ip_addr("wlan0")
            self.lcd.message("IP-Adresse:\n%s" % ip)
        elif option is None:
            self.mode = self.previous_mode_menu
            self.previous_mode_menu = None
            self.resume()

    def resume(self):
        print("Resume mode %s" % self.mode)
        getattr(self, self.mode)()

    def logout_packer(self):
        print("Logged out packer")

        self.lcd.message("Verbinde...")
        self.ws.call("Packaging", "logoutPacker", {"packer": self.packer_id, "terminal": self.terminal_id})

        self.select_packer()

    def select_packer(self):
        self.mode = self.MODE_SELECT_PACKER
        self.packer_id = None
        self.sel.show("Packernummer:")

    def wait_invoice(self):
        self.mode = self.MODE_WAIT_INVOICE
        self.invoice = None

        if self.scanner is None:
            self.lcd.message("Kein Barcode-\nscanner gefunden")
        else:
            self.lcd.message("Lieferschein\nscannen")

    def start_tracking(self):
        self.lcd.message("Verbinde...")

        result = self.ws.call("Packaging", "getOrderInfo", {"orderId": self.invoice})

        if result["_success"]:
            self.start_time = time()
            self.mode = self.MODE_TRACKING

            self.order_info = "%s %s" % (result["first_name"], result["last_name"])
            self.resume_tracking()
        else:
            self.lcd.message(result["_status"])
            sleep(1)
            self.wait_invoice()

    def resume_tracking(self):
        self.timer_event.set()

    def end_tracking(self):
        pack_time = int(time() - self.start_time)

        self.lcd.message("Verbinde...")
        self.start_time = None

        result = self.ws.call("Packaging", "finishParcel", {
            "orderId": self.invoice,
            "packTime": pack_time,
            "packerId": self.packer_id,
        })

        if result["_success"]:
            self.lcd.message("Gepackte Zeit:\n%s Minuten" % self.format_time(pack_time))
        else:
            self.lcd.message("Fehlgeschlagen")

        sleep(2)
        self.wait_invoice()

    def select_packer_callback(self, number):
        self.lcd.message("Verbinde...")
        result = self.ws.call("Packaging", "loginPacker", {"packerId": number})

        if result["_success"]:
            self.packer_id = result["packer_id"]
            self.lcd.message("Hallo,\n%s!" % result["name"].encode("ascii", "replace"))

            sleep(1)

            self.mode = self.MODE_WAIT_INVOICE
            self.resume()
        else:
            self.lcd.message("Unbekannte\nNummer")
            sleep(1)
            self.sel.show(self.sel.prompt)

    def quit(self, restart=False):
        if restart:
            exit(200)
        else:
            self.lcd.message("Auf\nWiedersehen!")
            sleep(2)
            exit()

    def shutdown(self):
        print("Shutting down...")
        self.lcd.message("Fahre\nherunter")
        system("/sbin/shutdown -h now")

    def __setattr__(self, key, value):
        def color(col, text):
            return "\033[%dm%s\033[0m" % (col, text)

        if (key == "mode" or key.startswith("previous_mode")) and hasattr(self, key):
            if getattr(self, key) != value:
                print("Switching %s from %s to %s." % (color(31, key), color(32, getattr(self, key)), color(33, value)))

        object.__setattr__(self, key, value)

    @staticmethod
    def format_time(seconds):
        return "%d:%02d" % (floor(seconds / 60), seconds % 60)

    @staticmethod
    def parse_invoice_barcode(barcode):
        if len(barcode) != 13:
            return barcode

        invoice = barcode[1:-1]
        return invoice.strip("0")


if __name__ == "__main__":
    lcd = CharLCDPlate()
    lcd.begin(16, 2)

    try:
        settings = Settings()
        tracker = PackingTimeTracker(settings, lcd)

        atexit.register(lcd.message, "Programm\nbeendet")

        tracker.select_packer()
        tracker.start()

    except NoDeviceFoundError:
        lcd.message("Kein Barcode-\nscanner gefunden")
        exit(200)

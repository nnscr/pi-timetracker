from threading import Thread, Lock, Semaphore
from time import time
from CharLCDPlate import NumberSelector, CharLCDPlate, Menu
from gaia.webservice.Webservice import Webservice
from gaia.webservice.Settings import Settings
from time import sleep
from barcode_scanner import BarcodeScanner

# Threads:
#  Barcodescanner
#  Tastenabfrage Tastatur
#  Hauptthread


class PackingTimeTracker(object):
    MODE_SELECT_PACKER = 1
    MODE_WAIT_INVOICE = 2
    MODE_TRACKING = 3
    MODE_MENU = 4

    EVENT_BARCODE = 1
    EVENT_BUTTON = 2

    def __init__(self, settings, lcd):
        self.settings = settings
        self.lcd = lcd
        self.sel = NumberSelector(self.lcd)
        self.menu = Menu(self.lcd)
        self.scanner = BarcodeScanner.find_scanner()
        self.mode = self.MODE_SELECT_PACKER
        self.previous_mode = None

        self.ws = Webservice(self.settings.get("url"))
        self.ws.token = self.settings.get("token")
        self.ws.username = self.settings.get("username")
        self.ws.password = self.settings.get("password")

        self.scanner_thread = Thread(target=self.scanner_thread, name="scanner_thread")
        self.buttons_thread = Thread(target=self.buttons_thread, name="buttons_thread")
        self.scanner_thread.daemon = True
        self.buttons_thread.daemon = True

        self.lock = Lock()
        self.semaphore = Semaphore()

        self.event_stack = list()

        self.packer_id = None
        self.invoice = None
        self.start_time = None

    def scanner_thread(self):
        while True:
            barcode = self.scanner.read()

            self.lock.acquire()
            self.event_stack.append((self.EVENT_BARCODE, barcode))
            self.semaphore.release()
            self.lock.release()

    def buttons_thread(self):
        while True:
            button = self.lcd.read_buttons()

            self.lock.acquire()
            self.event_stack.append((self.EVENT_BUTTON, button))
            self.semaphore.release()
            self.lock.release()

    def start(self):
        self.scanner_thread.start()
        self.buttons_thread.start()

        while self.semaphore.acquire():
            self.lock.acquire()
            for event in self.event_stack:
                type, value = event

                if type == self.EVENT_BARCODE:
                    self.barcode_entered(value)
                elif type == self.EVENT_BUTTON:
                    self.button_pressed(value)

                self.event_stack.remove(event)
            self.lock.release()

    def barcode_entered(self, barcode):
        print("Barcode entered: %s" % barcode)

        if self.mode == self.MODE_SELECT_PACKER:
            self.select_packer_callback(barcode)

        elif self.mode == self.MODE_WAIT_INVOICE:
            self.invoice = barcode
            self.start_tracking()

        elif self.mode == self.MODE_TRACKING:
            self.end_tracking()

    def button_pressed(self, button):
        print("Button pressed: %s" % button)

        if self.mode == self.MODE_SELECT_PACKER:
            self.sel.on_button_press(button)

        elif self.mode == self.MODE_MENU:
            self.menu.button_pressed(button)

        else:
            self.previous_mode = self.mode
            self.mode = self.MODE_MENU
            self.menu.show([
                ("select_packer", "Abmelden"),
                ("abort", "Paket\nabbrechen"),
            ])

    def select_packer(self):
        self.mode = self.MODE_SELECT_PACKER
        self.packer_id = None
        self.sel.callback = self.select_packer_callback
        self.sel.show("Packernummer:")

    def wait_invoice(self):
        self.mode = self.MODE_WAIT_INVOICE
        self.lcd.message("Lieferschein\nscannen")

    def start_tracking(self):
        self.mode = self.MODE_TRACKING
        self.start_time = time()
        self.lcd.message("Verbinde...")

        result = self.ws.call("Packaging", "getOrderInfo", {"orderId": self.invoice})
        print result

        if result["_success"]:
            self.lcd.message("%s\n%s" % (result["first_name"], result["last_name"]))
        else:
            self.lcd.message(result["_status"])

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
            self.lcd.message("Gepackte Zeit:\n%d Sekunden" % pack_time)
        else:
            self.lcd.message("Fehlgeschlagen")

        sleep(2)
        self.wait_invoice()

    def select_packer_callback(self, number):
        self.lcd.message("Verbinde...")
        result = self.ws.call("Packaging", "getPackerInfo", {"packerId": number})

        if result["_success"]:
            self.packer_id = result["packer_id"]
            self.lcd.message("Hallo,\n%s!" % result["name"].encode("ascii", "replace"))
            sleep(1)
            self.wait_invoice()
        else:
            self.lcd.message("Unbekannte\nNummer")
            sleep(1)
            self.sel.show(self.sel.prompt)

if __name__ == "__main__":
    lcd = CharLCDPlate()

    try:
        settings = Settings()
        tracker = PackingTimeTracker(settings, lcd)
        tracker.select_packer()
        tracker.start()
    except:
        lcd.message("Programm\nbeendet")
        raise


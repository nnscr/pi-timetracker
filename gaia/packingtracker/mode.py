from gaia.packingtracker.common import AppState
from show_ip_addr import get_ip_addr
from math import floor
from time import sleep
from gaia.drivers.CharLCDPlate import NumberSelector, MenuBuilder


class Mode(object):
    def __init__(self, app_state):
        self.app_state = app_state
        self.lcd = app_state.lcd

    def draw(self):
        pass

    def handle_event(self, event, value):
        pass

    def finished(self, value):
        self.app_state.add_event(AppState.EVENT_FINISH, value)

    def finish(self, value):
        pass

    def on_enter(self, old_mode):
        pass

    def on_tick(self):
        pass

    def on_menu_tick(self):
        pass

    def on_exit(self, new_mode):
        pass


class SelectPacker(Mode):
    def __init__(self, app_state):
        assert isinstance(app_state, AppState)

        Mode.__init__(self, app_state)

        self.sel = NumberSelector(self.lcd)
        self.sel.callback = self.callback

        self.is_connecting = False

    def draw(self):
        if self.is_connecting:
            self.lcd.message("Verbinde...")
        else:
            self.sel.show("Packernummer:")

    def finish(self, num):
        return WaitInvoice(self.app_state)

    def callback(self, num):
        self.app_state.call_ws_async(self.network_callback, "Packaging", "loginPacker", {
            "packer": num,
            "machine": self.app_state.machine
        })
        self.is_connecting = True
        self.draw()

    def handle_event(self, event, value):
        if event == AppState.EVENT_BUTTON:
            self.sel.on_button_press(value)

        elif event == AppState.EVENT_BARCODE:
            self.callback(value)

    def network_callback(self, result):
        self.is_connecting = False

        if result["_success"]:
            self.app_state.set_packer(result["packer_id"], result["name"])
            self.app_state.breakdown = result["broken"]

            self.lcd.message("Hallo,\n%s!" % result["name"].encode("ascii", "replace"))
            sleep(1)
            self.finished(result["packer_id"])

        else:
            self.lcd.message("Unbekannte\nNummer")
            sleep(1)
            self.sel.show(self.sel.prompt)


class WaitInvoice(Mode):
    def __init__(self, app_state):
        Mode.__init__(self, app_state)

        self.is_connecting = False
        self.scroll_text_position = 0
        self.messages = list()
        self.last_count = None

        # Prepare this for the first draw
        self.on_tick()

    def on_tick(self):
        self.messages = list()

        if self.is_connecting:
            self.messages.append("Verbinde...")

        if not self.app_state.has_scanner:
            self.messages.append("Kein Barcode-\nscanner gefunden")

        else:
            self.messages.append("Lieferschein\nscannen")

        if self.app_state.breakdown:
            self.messages.append("Ausfall\ngemeldet")

        count = len(self.messages) - 1

        # Scroll through the messages
        if self.scroll_text_position >= count:
            self.scroll_text_position = 0

        else:
            self.scroll_text_position += 1

        if len(self.messages) > 1 or self.last_count != count:
            self.draw()

        self.last_count = count

    def draw(self):
        self.lcd.message(self.messages[self.scroll_text_position])

    def handle_event(self, event, value):
        if event == AppState.EVENT_DEVICE:
            self.draw()

        elif event == AppState.EVENT_BARCODE:
            invoice = self.parse_invoice_barcode(value)
            self.app_state.call_ws_async(self.network_callback, "Packaging", "startTracking", {
                "order": invoice,
                "machine": self.app_state.machine
            })
            self.is_connecting = True
            self.draw()

        elif event == AppState.EVENT_BUTTON:
            self.app_state.switch_mode(Menu(self.app_state, self))

    def network_callback(self, result):
        self.is_connecting = False

        if result["_success"]:
            order_info = "%s %s" % (result["first_name"], result["last_name"])
            self.finished((order_info, result["order_id"]))

        else:
            self.lcd.message(result["_status"])
            sleep(1)
            self.draw()

    def finish(self, value):
        order_info, invoice = value

        t = Tracking(self.app_state)
        t.invoice = invoice
        t.order_info = order_info

        return t

    @staticmethod
    def parse_invoice_barcode(barcode):
        if len(barcode) != 13:
            return barcode

        invoice = barcode[1:-1]
        return invoice.lstrip("0")


class Tracking(Mode):
    def __init__(self, director):
        Mode.__init__(self, director)

        self.invoice = None
        self.order_info = None
        self.is_connecting = False
        self.is_paused = False
        self.time = 0

    def on_tick(self):
        self.draw()
        self.on_menu_tick()

    def on_menu_tick(self):
        if not self.is_paused:
            self.time += 1

    def pause(self, pause=None):
        if pause is None:
            pause = not self.is_paused

        self.is_paused = pause

    def draw(self):
        warning = ""

        warning += "S" if not self.app_state.has_scanner else " "
        warning += "A" if self.app_state.breakdown else " "

        line1 = "{:<6}{:^4}{:>6}".format(self.get_time(), warning, self.invoice)
        line2 = self.order_info

        self.lcd.message("\n".join((line1, line2)))

    def get_time(self):
        return "%d:%02d" % (floor(self.time / 60), self.time % 60)

    def handle_event(self, event, value):
        if event == AppState.EVENT_DEVICE:
            self.draw()

        elif event == AppState.EVENT_BARCODE:
            self.barcode_entered(value)

        elif event == AppState.EVENT_BUTTON:
            if value == self.lcd.SELECT:
                self.pause()

            else:
                self.app_state.switch_mode(Menu(self.app_state, self))

    def barcode_entered(self, value):
        self.app_state.call_ws_async(self.network_callback, "Packaging", "finishParcel", {
            "order": self.invoice,
            "packTime": self.time,
            "packer": self.app_state.packer_id,
            "machine": self.app_state.machine,
            })

    def network_callback(self, response):
        self.finished(response)

    def finish(self, value):
        return WaitInvoice(self.app_state)


class Menu(Mode):
    def __init__(self, app_state, previous_mode):
        Mode.__init__(self, app_state)

        self.previous_mode = previous_mode

        self.menu_builder = MenuBuilder(self.lcd)
        self.menu_builder.callback = self.callback
        self.menu_builder.options = list()

        if self.app_state.is_tracking():
            self.menu_builder.options.append(("abort", "Paket\nabbrechen"))

        self.menu_builder.options.append(("logout", "Abmelden"))

        if self.app_state.machine is not None:
            if self.app_state.breakdown:
                self.menu_builder.options.append(("repaired", "Ausfall\nbehoben"))
            else:
                self.menu_builder.options.append(("breakdown", "Ausfall\nmelden"))

        self.menu_builder.options.append(("show_ip", "IP-Adresse\nanzeigen"))
        self.menu_builder.options.append(("shutdown", "Herunterfahren"))

    def on_tick(self):
        self.previous_mode.on_menu_tick()

    def callback(self, option):
        if option == "show_ip":
            ip = get_ip_addr("wlan0")
            self.lcd.message("IP-Adresse:\n%s" % ip)

        else:
            self.finished(option)

    def finish(self, option):
        if option is None:
            # Cancel button pressed, return to previous mode
            return self.previous_mode

        if option == "logout":
            self.app_state.call_ws_async(None, "Packaging", "logoutPacker", {
                "packer": self.app_state.packer_id,
                "machine": self.app_state.machine,
            })

            return SelectPacker(self.app_state)

        if option == "quit":
            self.app_state.add_event(AppState.EVENT_QUIT, None)
            return

        if option == "abort":
            return WaitInvoice(self.app_state)

        if option == "shutdown":
            self.app_state.shutdown_system()
            return

        if option == "breakdown":
            self.app_state.call_ws_async(None, "Packaging", "reportBreakdown", {"machine": self.app_state.machine})
            return self.previous_mode

        if option == "repaired":
            self.app_state.call_ws_async(None, "Packaging", "repairedMachine", {"machine": self.app_state.machine})
            return self.previous_mode

    def draw(self):
        self.menu_builder.draw()

    def handle_event(self, event, value):
        if event == AppState.EVENT_BUTTON:
            self.menu_builder.button_pressed(value)

#!/usr/bin/python
# coding=utf-8
from CharLCDPlate import NumberSelector, CharLCDPlate
from gaia.webservice.Webservice import Webservice
from gaia.webservice.Settings import Settings
from time import sleep
from barcode_scanner import BarcodeScanner


# Configuration
settings = Settings()
lcd = CharLCDPlate()
sel = NumberSelector(lcd)
scanner = BarcodeScanner.find_scanner()

# Create webservice and set last token from configuration
ws = Webservice(settings.get("url"))
ws.token = settings.get("token")
ws.username = settings.get("username")
ws.password = settings.get("password")


def packer_selected_callback(ws):
    def callback(sel, number):
        result = ws.call("Packaging", "getPackerInfo", {"packerId": number})
        print(result)

        lcd.clear()

        if result["_success"]:
            lcd.message("Hallo,\n%s!" % result["name"].encode("ascii", "replace"))
        else:
            lcd.message("Unbekannte\nNummer")
            sleep(1)
            sel.show(sel.prompt)

    return callback

# Show welcome message
lcd.clear()
lcd.message("Willkommen!")
sleep(3)

# Show number selector
sel.callback = packer_selected_callback(ws)
sel.show("Packernummer:")

while True:
    barcode = scanner.read()

    response = ws.call("Packaging", "findItemByEAN", {"ean": barcode})

    lcd.clear()
    if not response["_success"]:
        lcd.message("Nicht gefunden")
    else:
        lcd.message(barcode + "\n" + response["name"])

# Make a call
#response = ws.call("Packaging", "finishParcel", {'orderId': 1234})
#lcd.message(response["order_id"])

settings.set("token", ws.token)
settings.write()

# Erfassungsgerät fährt hoch, startet Programm
# Packernummer wird ausgewählt (NumberSelector)
# Der Name wird zur Bestätigung angezeigt
# Es wird ein Rechnungsbarcode erfasst
# Die bereits gepackte Zeit + Order ID wird angezeigt
# Es wird eine Sendungsnummer erfasst


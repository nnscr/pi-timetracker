# Packing time tracker power on self test

from RPi import GPIO
from time import sleep
from gaia.packingtracker.common import AppState

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

red = 11
ylw = 13
grn = 15

GPIO.setup(red, GPIO.OUT)
GPIO.setup(ylw, GPIO.OUT)
GPIO.setup(grn, GPIO.OUT)

for led in (red, grn, ylw):
    GPIO.output(led, False)

sleep(0.75)
GPIO.output(red, True)
sleep(0.75)
GPIO.output(ylw, True)
sleep(0.75)
GPIO.output(grn, True)
sleep(0.75)

GPIO.output(grn, False)
GPIO.output(ylw, False)

# Leave the power led turned on until shutdown where it is automatically powered off.
# GPIO.output(AppState.LED_RED, True)

# Packing time tracker power on self test

from RPi import GPIO
from time import sleep
from gaia.packingtracker.common import AppState

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

GPIO.setup(AppState.LED_RED, GPIO.OUT)
GPIO.setup(AppState.LED_YLW, GPIO.OUT)
GPIO.setup(AppState.LED_GRN, GPIO.OUT)

for led in (AppState.LED_RED, AppState.LED_GRN, AppState.LED_YLW):
    GPIO.output(led, False)

sleep(0.75)
GPIO.output(AppState.LED_RED, True)
sleep(0.75)
GPIO.output(AppState.LED_YLW, True)
sleep(0.75)
GPIO.output(AppState.LED_GRN, True)
sleep(0.75)

GPIO.output(AppState.LED_GRN, False)
GPIO.output(AppState.LED_YLW, False)

# Leave the power led turned on until shutdown where it is automatically powered off.
# GPIO.output(AppState.LED_RED, True)

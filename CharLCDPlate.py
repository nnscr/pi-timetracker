from Adafruit_CharLCDPlate import Adafruit_CharLCDPlate
from time import sleep

__author__ = 'philipp'


class CharLCDPlate(Adafruit_CharLCDPlate):
    def __init__(self):
        Adafruit_CharLCDPlate.__init__(self)
        self.previous_button = None

    def read_buttons(self):
        if self.previous_button is not None and not self.buttonPressed(self.previous_button):
            self.previous_button = None

        for button in (self.LEFT, self.UP, self.RIGHT, self.DOWN, self.SELECT):
            if self.buttonPressed(button) and button is not self.previous_button:
                self.previous_button = button
                return button

        return None

    def message(self, text, clear=True):
        if clear:
            self.clear()

        Adafruit_CharLCDPlate.message(self, text)


class Menu(object):
    def __init__(self, lcd):
        self.lcd = lcd
        self.cursor = None
        self.options = None
        self.callback = None

    def show(self, options):
        self.options = options
        self.cursor = 0
        self.draw()

    def draw(self):
        captions = map(lambda o: o[1], self.options)
        self.lcd.message(captions[self.cursor])

    def button_pressed(self, button):
        if button == self.lcd.UP:
            # Move cursor up
            if self.cursor == 0:
                self.cursor = len(self.options)

            self.cursor -= 1
            self.draw()

        elif button == self.lcd.DOWN:
            # Move cursor down
            if self.cursor == len(self.options) - 1:
                self.cursor = 0
            else:
                self.cursor += 1
            self.draw()

        elif button in (self.lcd.RIGHT, self.lcd.SELECT):
            # Select option
            self.callback(self.options[self.cursor][0])

        elif button == self.lcd.LEFT:
            # Cancel
            self.callback(None)


class NumberSelector(object):
    def __init__(self, lcd):
        self.lcd = lcd
        self.current = 0
        self.position = 1
        self.callback = None
        self.prompt = None

    def show(self, prompt):
        self.prompt = prompt
        self.draw()

    def on_button_press(self, button):
        if button == self.lcd.LEFT:
            self.position += 1
            self.flash()
        elif button == self.lcd.RIGHT:
            if self.position > 1:
                self.position -= 1
            self.flash()
        elif button == self.lcd.SELECT:
            value = self.current
            self.position = 1
            self.current = 0
            self.callback(value)
        elif button == self.lcd.UP:
            line = list("%016d" % self.current)
            digit = int(line[-self.position])

            if digit < 9:
                digit += 1
            else:
                digit = 0

            line[-self.position] = str(digit)

            self.current = int("".join(line))

            self.draw()
        elif button == self.lcd.DOWN:
            line = list("%016d" % self.current)
            digit = int(line[-self.position])

            if digit > 0:
                digit -= 1
            else:
                digit = 9

            line[-self.position] = str(digit)

            self.current = int("".join(line))
            self.draw()

    def draw(self, line1=None, line2=None):
        line1 = self.prompt if line1 is None else line1
        line2 = self.current if line2 is None else line2
        self.lcd.message("%-16s\n%16s" % (line1, line2))

    def flash(self, position=None):
        if position is None:
            position = self.position

        line1 = self.prompt
        line2 = list("%16s" % self.current)

        line2[-position] = "_"

        line2 = "".join(line2)

        self.draw(line1, line2)
        sleep(.5)
        self.draw()

if __name__ == "__main__":
    lcd = CharLCDPlate()
    sel = NumberSelector(lcd)

    def test_callback(number):
        print("Selected number: %d" % number)
        lcd.message("Selected Number:\n%d" % number)

    sel.callback = test_callback

    sel.show("Number:")

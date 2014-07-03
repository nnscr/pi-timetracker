from evdev import InputDevice, list_devices, ecodes, KeyEvent, categorize


class NoDeviceFoundError(Exception):
    pass


class BarcodeScanner(object):
    scancodes = {
        2: "1",
        3: "2",
        4: "3",
        5: "4",
        6: "5",
        7: "6",
        8: "7",
        9: "8",
        10: "9",
        11: "0",
    }

    def __init__(self, fd):
        self.fd = fd
        self.dev = InputDevice(fd)
        self.buffer = list()

    @staticmethod
    def find_scanner():
        """Get a BarcodeScanner instance or raise a NoDeviceFoundError if no barcode scanner was found."""
        scanner = BarcodeScanner.get_scanner()

        if scanner:
            return scanner

        raise NoDeviceFoundError

    @staticmethod
    def get_scanner():
        """Get a BarcodeScanner instance or return None if no barcode scanner was found."""
        devices = map(InputDevice, list_devices())

        for dev in devices:
            if ecodes.EV_KEY in dev.capabilities():
                return BarcodeScanner(dev.fn)

        return None

    def read(self):
        try:
            for event in self.dev.read_loop():
                kevent = KeyEvent(event)
                if event.type == ecodes.EV_KEY and kevent.keystate == kevent.key_up:
                    if event.code == ecodes.KEY_ENTER:
                        barcode = self.buffer
                        self.buffer = list()

                        return "".join(barcode)

                    else:
                        try:
                            self.buffer.append(self.scancodes[event.code])

                        except KeyError:
                            print(categorize(event))
        except IOError, e:
            if e.errno == 19:
                raise NoDeviceFoundError


if __name__ == "__main__":
    try:
        scanner = BarcodeScanner.find_scanner()

        while True:
            code = scanner.read()
            print(code)

    except NoDeviceFoundError:
        print("No barcode scanner device found.")



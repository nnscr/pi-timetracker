import socket
import fcntl
import struct
from CharLCDPlate import CharLCDPlate

SIOCGIFADDR = 0x8915


def get_ip_addr(iface):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(s.fileno(), SIOCGIFADDR, struct.pack('256s', iface[:15]))[20:24])


if __name__ == "__main__":
    lcd = CharLCDPlate()
    ip = get_ip_addr("wlan0")

    lcd.message("IP-Addresse:\n%s" % ip)

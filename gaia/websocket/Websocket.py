from _socket import error
import base64
import os
from select import select
import socket
import random
import json


class ConnectionError(BaseException):
    pass


class NotConnected(BaseException):
    pass


class IncomingResponse(object):
    POS_FIRST = 1
    POS_SECOND = 2
    POS_PAYLOAD = 3

    recvbuf = []
    length = None
    bytes = 0
    pos = POS_FIRST

    def buffer(self, b):
        self.bytes += 1
        self.recvbuf.append(b)

    def is_ready(self):
        return self.bytes >= self.length

    def finish(self):
        msg = "".join([chr(b) for b in self.recvbuf])

        self.recvbuf = []
        self.length = None
        self.pos = self.POS_FIRST
        self.bytes = 0

        return msg

    def awaiting_length(self):
        return self.length is None

    def received(self, data):
        for byte in data:
            rsp = self.received_byte(ord(byte))

            if rsp:
                return rsp

        return None

    def received_byte(self, byte):
        if self.pos == self.POS_FIRST:
            # discard first byte
            self.pos = self.POS_SECOND
            return

        if self.pos == self.POS_SECOND:
            self.length = byte
            self.pos = self.POS_PAYLOAD
            return

        if self.pos == self.POS_PAYLOAD:
            self.buffer(byte)

            if self.is_ready():
                # End message
                message = self.finish()

                response = json.loads(message)
                return response

        return


class Websocket:
    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.token = None
        self.username = None
        self.password = None

        self.is_connected = False
        self.message_id = 0

        self.inc = IncomingResponse()

        self.pipe = os.pipe()

    @staticmethod
    def gen_nonce():
        nonce = ""

        while len(nonce) < 16:
            nonce += chr(random.randrange(1, 254))

        return base64.b64encode(nonce)

    def next_message_id(self):
        self.message_id += 1

        return self.message_id

    def connect(self):
        print(self.endpoint)
        self.socket.connect(self.endpoint)

        self.socket.send("GET /open HTTP/1.1\r\n")
        self.socket.send("Host: %s:%d\r\n" % self.endpoint)
        self.socket.send("Upgrade: websocket\r\n")
        self.socket.send("Connection: Upgrade\r\n")
        self.socket.send("Origin: http://%s\r\n" % self.endpoint[0])
        self.socket.send("Sec-WebSocket-Key: %s\r\n" % self.gen_nonce())
        self.socket.send("Sec-WebSocket-Version: 13\r\n")
        self.socket.send("\r\n")

        buf = ""

        self.socket.setblocking(True)

        while True:
            b = self.socket.recv(1)

            if not b:
                raise ConnectionError("Error while receiving the HTTP header")

            if b == "\n" and buf.endswith("\r\n\r"):
                break

            buf += b

        self.socket.setblocking(False)
        self.is_connected = True

    def send(self, obj):
        return self.send_raw(json.dumps(obj))

    def send_raw(self, raw):
        buf = [0x81]  # opcode 0x81 = text

        length = len(raw)

        if length <= 125:
            buf.append(length | 0x80)  # 0x80 = payload masked, required for client -> server communication

        elif 126 <= length <= 65535:
            buf.append(0xFE)
            buf.append((length >> 8) & 0xFF)
            buf.append(length & 0xFF)

        else:
            buf.append(0xFF)
            buf.append((length >> 56) & 0xFF)
            buf.append((length >> 48) & 0xFF)
            buf.append((length >> 40) & 0xFF)
            buf.append((length >> 32) & 0xFF)
            buf.append((length >> 24) & 0xFF)
            buf.append((length >> 16) & 0xFF)
            buf.append((length >> 8) & 0xFF)
            buf.append(length & 0xFF)

        mask = [random.randrange(0, 0xFF) for i in range(0, 4)]

        for b in mask:
            buf.append(b)

        for i, b in enumerate(raw):
            encoded = ord(b) ^ mask[i % 4]
            buf.append(encoded)

        self.socket.send("".join([chr(b) for b in buf]))

    def call(self, extension, procedure, parameters={}):
        if not self.is_connected:
            raise NotConnected

        msgid = self.next_message_id()

        self.send([5, [extension, procedure, parameters], msgid])

        return msgid

    def auth(self, token=None):
        if not token:
            token = self.token

        self.send([1, token, "auth"])

    def login(self, username=None, password=None):
        if not username:
            username = self.username

        if not password:
            password = self.password

        self.send([1, [username, password], "login"])

    def subscribe(self, channel):
        self.send([3, channel, None])

    def interrupt(self):
        os.write(self.pipe[1], "interrupt")

    def wait_response(self):
        sel = [self.socket]

        read, write, err = select(sel + [self.pipe[0]], sel, sel)

        for sock in read:
            while True:
                try:
                    data = sock.recv(1)

                    response = self.inc.received_byte(ord(data))

                    if response:
                        return response

                except (error, AttributeError):
                    break

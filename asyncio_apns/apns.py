import asyncio
import json
import ssl
import struct
from binascii import unhexlify

PRODUCTION_SERVER_ADDR = 'gateway.push.apple.com'
SANDBOX_SERVER_ADDR = 'gateway.sandbox.push.apple.com'
SERVER_PORT = 2195


def _apns_pack_frame(token_hex, payload, identifier, expiration, priority):
    """
    copy-paste from https://github.com/jleclanche/django-push-notifications/blob/master/push_notifications/apns.py
    """
    token = unhexlify(token_hex)
    # |COMMAND|FRAME-LEN|{token}|{payload}|{id:4}|{expiration:4}|{priority:1}
    frame_len = 3 * 5 + len(token) + len(payload) + 4 + 4 + 1  # 5 items, each 3 bytes prefix, then each item length
    frame_fmt = "!BIBH%ssBH%ssBHIBHIBHB" % (len(token), len(payload))
    frame = struct.pack(
        frame_fmt,
        2, frame_len,
        1, len(token), token,
        2, len(payload), payload,
        3, 4, identifier,
        4, 4, expiration,
        5, 1, priority)

    return frame


class ApnsClient:
    def __init__(self, cert_file: str, key_file: str, sandbox=False, loop=None):
        self.cert_file = cert_file
        self.key_file = key_file
        self.sandbox = sandbox
        self._loop = loop
        self._connection = None

    @asyncio.coroutine
    def connect(self):
        host = SANDBOX_SERVER_ADDR if self.sandbox else PRODUCTION_SERVER_ADDR
        context = ssl.create_default_context()
        context.load_cert_chain(self.cert_file, self.key_file)
        reader, writer = yield from asyncio.open_connection(
            host, SERVER_PORT, ssl=context, loop=self._loop)
        self._connection = Connection(reader, writer, self._loop)

    @asyncio.coroutine
    def send_message(self, message: str, token: str):
        if self._connection is None or self._connection.closed():
            yield from self.connect()
        data = dict(aps={'alert': message})
        payload = json.dumps(data).encode()
        frame = _apns_pack_frame(token, payload, 0, 0, 10)
        self._connection.write(frame)

    def disconnect(self):
        self._connection.close()
        self._connection = None


class Connection:
    def __init__(self, reader, writer, loop=None):
        self.reader = reader
        self.writer = writer
        self._loop = loop

    @property
    def closed(self) -> bool:
        return self.reader.at_eof()

    def close(self):
        self.writer.close()

    def write(self, data: bytes):
        self.writer.write(data)

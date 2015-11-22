import asyncio
import ssl
import struct
from binascii import hexlify
from collections import namedtuple

PRODUCTION_SERVER_ADDR = 'feedback.push.apple.com'
SANDBOX_SERVER_ADDR = 'feedback.sandbox.push.apple.com'
SERVER_PORT = 2196


FeedbackElement = namedtuple('FeedbackElement', ['timestamp', 'token'])


@asyncio.coroutine
def feedback_connect(cert_file: str, key_file: str, *, sandbox=False, loop=None):
    client = FeedbackClient(cert_file, key_file, sandbox=sandbox, loop=loop)
    yield from client.connect()
    return client


class FeedbackClient:
    def __init__(self, cert_file: str, key_file: str, *, sandbox=False, loop=None):
        self.cert_file = cert_file
        self.key_file = key_file
        self.sandbox = sandbox
        self._loop = loop
        self.reader = None
        self.writer = None

    @asyncio.coroutine
    def connect(self):
        host = SANDBOX_SERVER_ADDR if self.sandbox else PRODUCTION_SERVER_ADDR
        context = ssl.create_default_context()
        context.load_cert_chain(self.cert_file, self.key_file)
        self.reader, self.writer = yield from asyncio.open_connection(
            host, SERVER_PORT, ssl=context, loop=self._loop)

    def diconnect(self):
        self.writer.close()
        self.writer = None
        self.reader = None

    @asyncio.coroutine
    def _read_by_format(self, format: str) -> bytes:
        try:
            data = yield from self.reader.readexactly(struct.calcsize(format))
            data = struct.unpack(format, data)
        except asyncio.IncompleteReadError:
            data = None
        return data

    @asyncio.coroutine
    def _fetch_next(self):
        header_format = '!LH'
        data = yield from self._read_by_format(header_format)
        if data is None:
            return None
        timestamp, token_length = data
        token_format = '{}s'.format(token_length)
        device_token, *_ = yield from self._read_by_format(token_format)
        if device_token is None:
            return None
        return FeedbackElement(timestamp, hexlify(device_token))

    @asyncio.coroutine
    def fetch_all(self):
        elements = []
        if self.reader is None or self.reader.at_eof():
            return elements
        while True:
            element = yield from self._fetch_next()
            if element is None:
                break
            elements.append(element)
        return elements

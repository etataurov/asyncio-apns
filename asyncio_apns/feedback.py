import asyncio
import ssl
from binascii import hexlify
from collections import namedtuple

from .apns_protocol import FEEDBACK_HEADER_FORMAT, token_format
from .connection import Connection

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
        self._connection = None

    @asyncio.coroutine
    def connect(self):
        host = SANDBOX_SERVER_ADDR if self.sandbox else PRODUCTION_SERVER_ADDR
        context = ssl.create_default_context()
        context.load_cert_chain(self.cert_file, self.key_file)
        reader, writer = yield from asyncio.open_connection(
            host, SERVER_PORT, ssl=context, loop=self._loop)
        self._connection = Connection(reader, writer, loop=self._loop)

    def diconnect(self):
        self._connection.close()
        self._connection = None

    @asyncio.coroutine
    def _fetch_next(self):
        data = yield from self._connection.read_by_format(
                FEEDBACK_HEADER_FORMAT)
        if data is None:
            return None
        timestamp, token_length = data
        device_token, *_ = yield from self._connection.read_by_format(
                token_format(token_length))
        if device_token is None:
            return None
        return FeedbackElement(timestamp, hexlify(device_token))

    @asyncio.coroutine
    def fetch_all(self):
        elements = []
        if self._connection.closed:
            return elements
        while True:
            element = yield from self._fetch_next()
            if element is None:
                break
            elements.append(element)
        return elements

__all__ = ["feedback_connect", "FeedbackClient"]

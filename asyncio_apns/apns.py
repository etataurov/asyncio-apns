import asyncio
import json
import ssl
import struct
from binascii import unhexlify
from collections import OrderedDict

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


@asyncio.coroutine
def connect(cert_file: str, key_file: str, *, sandbox=False, loop=None):
    client = ApnsClient(cert_file, key_file, sandbox=sandbox, loop=loop)
    yield from client.connect()
    return client


class ApnsError(Exception):
    def __init__(self, status, identifier):
        super().__init__()
        self.status = status
        self.identifier = identifier

    def __repr__(self):
        return "ApnsError(status={}, identifier={})".format(
            self.status, self.identifier)

    def __str__(self):
        # TODO description from Apple
        return "ApnsError({})".format(self.status)

    def message_was_sent(self):
        # 10 - shutdown
        return self.status == 10


class ApnsDisconnectError(Exception):
    pass


class ErrorWaiter:
    def __init__(self, connection, *, loop=None):
        self._connection = connection
        self.waiters = OrderedDict()
        self._loop = loop
        self._read_future = None

    def start_waiting(self):
        self._read_future = asyncio.ensure_future(self.read())

    def stop(self):
        if self._read_future:
            self._read_future.cancel()
            self._read_future = None

    @asyncio.coroutine
    def read(self):
        error_format = "!BBI"
        data = yield from self._connection.read_by_format(error_format)
        if data is not None:
            command, status, identifier = data
            self.handle_error(identifier, status)
        else:
            # connection has been dropped
            self.handle_error()

    def handle_error(self, identifier=None, status=None):
        if identifier is None:
            mark_succeed = False
        else:
            mark_succeed = True
        for id_ in list(self.waiters.keys()):
            if id_ == identifier:
                mark_succeed = False
                self.failed(id_, ApnsError(status, identifier))
                continue
            if mark_succeed:
                self.succeed(id_)
            else:
                self.failed(id_, ApnsDisconnectError())

    def failed(self, message_id, error):
        data = self.waiters.pop(message_id, None)
        if data is not None:
            future, handle = data
            handle.cancel()
            future.set_exception(error)

    def succeed(self, message_id):
        data = self.waiters.pop(message_id, None)
        if data is not None:
            future, handle = data
            handle.cancel()
            future.set_result(None)

    def expect(self, message_id, timeout=5):
        f = asyncio.Future(loop=self._loop)
        loop = self._loop or asyncio.get_event_loop()
        handle = loop.call_later(timeout, self.succeed, message_id)
        self.waiters[message_id] = (f, handle)
        return f


class ApnsClient:
    def __init__(self, cert_file: str, key_file: str, *, sandbox=False, loop=None):
        self.cert_file = cert_file
        self.key_file = key_file
        self.sandbox = sandbox
        self._loop = loop
        self._connection = None
        self._waiter = None
        self._next_message_id = 0

    @asyncio.coroutine
    def connect(self):
        host = SANDBOX_SERVER_ADDR if self.sandbox else PRODUCTION_SERVER_ADDR
        context = ssl.create_default_context()
        context.load_cert_chain(self.cert_file, self.key_file)
        reader, writer = yield from asyncio.open_connection(
            host, SERVER_PORT, ssl=context, loop=self._loop)
        self._connection = Connection(reader, writer, loop=self._loop)
        self._waiter = ErrorWaiter(self._connection, self._loop)
        self._waiter.start_waiting()

    def disconnect(self):
        self._connection.close()
        self._connection = None
        self._waiter.stop()
        self._waiter = None

    @asyncio.coroutine
    def send_message(self, message: str, token: str, *, message_id=None):
        if self._connection is None or self._connection.closed:
            yield from self.connect()
        data = dict(aps={'alert': message})
        payload = json.dumps(data).encode()
        if message_id is None:
            message_id = self._next_message_id
            self._next_message_id += 1
        frame = _apns_pack_frame(token, payload, message_id, 0, 10)
        self._connection.write(frame)
        try:
            yield from self._connection.drain()
            yield from self._waiter.expect(message_id)
        except Exception:
            self.disconnect()
            raise


class Connection:
    def __init__(self, reader, writer, *, loop=None):
        self.reader = reader
        self.writer = writer
        self._loop = loop
        self._closed = False

    @property
    def closed(self) -> bool:
        return (self._closed or self.reader.at_eof() or
                self.reader.exception() is not None)

    def close(self):
        self._closed = True
        self.writer.close()

    @asyncio.coroutine
    def read_by_format(self, format: str) -> bytes:
        try:
            data = yield from self.reader.readexactly(struct.calcsize(format))
            data = struct.unpack(format, data)
        except asyncio.IncompleteReadError:
            data = None
        return data

    def write(self, data: bytes):
        self.writer.write(data)

    def drain(self):
        return self.writer.drain()

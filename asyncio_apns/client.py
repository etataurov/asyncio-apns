import asyncio
import json
import ssl
from collections import OrderedDict
from typing import Union

from .connection import Connection
from .errors import ApnsError, ApnsDisconnectError
from .payload import Payload
from .apns_protocol import ERROR_FORMAT, pack_frame

PRODUCTION_SERVER_ADDR = 'gateway.push.apple.com'
SANDBOX_SERVER_ADDR = 'gateway.sandbox.push.apple.com'
SERVER_PORT = 2195


@asyncio.coroutine
def connect(cert_file: str, key_file: str, *, sandbox=False, loop=None):
    client = ApnsClient(cert_file, key_file, sandbox=sandbox, loop=loop)
    yield from client.connect()
    return client


class ErrorWaiter:
    def __init__(self, connection, *, loop=None):
        self._connection = connection
        self.waiters = OrderedDict()
        self._loop = loop or asyncio.get_event_loop()
        self._read_future = None

    def start_waiting(self):
        self._read_future = self._loop.create_task(self.read())

    def stop(self):
        if self._read_future:
            self._read_future.cancel()
            self._read_future = None

    @asyncio.coroutine
    def read(self):
        data = yield from self._connection.read_by_format(ERROR_FORMAT)
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
        handle = self._loop.call_later(timeout, self.succeed, message_id)
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
        self._waiter = ErrorWaiter(self._connection, loop=self._loop)
        self._waiter.start_waiting()

    def disconnect(self):
        self._connection.close()
        self._connection = None
        self._waiter.stop()
        self._waiter = None

    @asyncio.coroutine
    def send_message(self, message: Union[Payload, str], token: str, *,
                     message_id=None, priority=10):
        if self._connection is None or self._connection.closed:
            yield from self.connect()
        if isinstance(message, Payload):
            payload = message
        else:
            payload = Payload(alert=message)
        data = json.dumps(payload.as_dict()).encode()
        if message_id is None:
            message_id = self._next_message_id
            self._next_message_id += 1
        frame = pack_frame(token, data, message_id, 0, priority)
        self._connection.write(frame)
        try:
            yield from self._connection.drain()
            yield from self._waiter.expect(message_id)
        except Exception:
            self.disconnect()
            raise


__all__ = ["connect", "ApnsClient"]

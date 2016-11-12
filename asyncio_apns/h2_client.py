import asyncio
import enum
import ssl
import collections
import json
from urllib.parse import urlsplit

from h2.connection import H2Connection, ConnectionState
from h2.events import (ConnectionTerminated, DataReceived,
                       ResponseReceived, StreamEnded, WindowUpdated)
from h2.exceptions import TooManyStreamsError


class HTTPMethod(enum.Enum):
    GET = "GET"
    POST = "POST"


class ExceptionJSONDataMixin:
    data = None

    def json_data(self):
        if self.data is not None:
            try:
                return json.loads(self.data.decode())
            except json.JSONDecodeError:
                return None


class HTTP2Error(Exception, ExceptionJSONDataMixin):
    def __init__(self, code, headers, data=None):
        self.code = code
        self.headers = headers
        self.data = data


class DisconnectError(Exception, ExceptionJSONDataMixin):
    def __init__(self, code, data=None):
        self.code = code
        self.data = data


class H2ClientProtocol(asyncio.Protocol):
    def __init__(self, connection=H2Connection()):
        self.conn = connection
        self.response_futures = dict()  # stream_id -> Future
        self.flow_control_futures = dict()  # stream_id -> Future
        self.stream_waiters = collections.deque()
        self.events_queue = collections.defaultdict(collections.deque)  # stream_id -> deque
        self.transport = None
        self.loop = None

    @property
    def connected(self):
        return self.transport is not None and not self.connection_closed()

    def connection_closed(self):
        return self.conn.state_machine.state == ConnectionState.CLOSED

    @classmethod
    @asyncio.coroutine
    def connect(cls, host: str, port: int,
                *, cert_file=None, key_file=None,
                verify_ssl=True, loop=None):
        if loop is None:
            loop = asyncio.get_event_loop()
        ssl_context = ssl.create_default_context()
        ssl_context.set_alpn_protocols(["h2"])
        if not verify_ssl:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        if cert_file and key_file:
            ssl_context.load_cert_chain(cert_file, key_file)
        # waiting for successful connect
        _, protocol = yield from loop.create_connection(H2ClientProtocol, host=host, port=port, ssl=ssl_context)
        protocol.loop = loop
        return protocol

    def disconnect(self):
        self.transport.close()

    def connection_made(self, transport):
        self.transport = transport
        self.conn.initiate_connection()
        self.transport.write(self.conn.data_to_send())

    def connection_lost(self, exc):
        self.on_terminated(None, None)
        self.transport = None

    def data_received(self, data):
        events = self.conn.receive_data(data)
        self.transport.write(self.conn.data_to_send())
        for event in events:
            if isinstance(event, ResponseReceived) or isinstance(event, DataReceived):
                self.events_queue[event.stream_id].append(event)
            elif isinstance(event, WindowUpdated):
                self.window_opened(event)
            elif isinstance(event, StreamEnded):
                self.events_queue[event.stream_id].append(event)
                self.handle_response(event.stream_id)
                self._on_stream_closed()
            elif isinstance(event, ConnectionTerminated):
                self.on_terminated(event.error_code, event.additional_data)

        data = self.conn.data_to_send()
        if data:
            self.transport.write(data)

    def on_terminated(self, error_code, data):
        while self.response_futures:
            _, f = self.response_futures.popitem()
            f.set_exception(DisconnectError(error_code, data))
        while self.stream_waiters:
            f = self.stream_waiters.popleft()
            f.set_exception(DisconnectError(error_code, data))

    def _on_stream_closed(self):
        if self.stream_waiters:
            future = self.stream_waiters.popleft()
            future.set_result(None)

    def window_opened(self, event):
        if event.stream_id:
            # This is specific to a single stream.
            if event.stream_id in self.flow_control_futures:
                future = self.flow_control_futures.pop(event.stream_id)
                future.set_result(None)
        else:
            # This event is specific to the connection. Free up *all* the
            # streams.

            for future in self.flow_control_futures.values():
                future.set_result(None)

            self.flow_control_futures = {}

    @asyncio.coroutine
    def send_request(self, headers, body=None):
        while True:
            try:
                stream_id = self.conn.get_next_available_stream_id()
                future = self._send_request(stream_id, headers, body)
                return (yield from future)
            except TooManyStreamsError:
                wait_future = asyncio.Future(loop=self.loop)
                self.stream_waiters.append(wait_future)
                yield from wait_future

    @asyncio.coroutine
    def _send_request_body(self, stream_id, body):
        while True:
            window_size = self.conn.local_flow_control_window(stream_id)

            available_window = min(window_size, len(body))
            data_to_send = body[:available_window]
            body = body[available_window:]

            chunk_size = self.conn.max_outbound_frame_size
            chunks = (
                data_to_send[x: x + chunk_size]
                for x in range(0, len(data_to_send), chunk_size)
            )
            for chunk in chunks:
                self.conn.send_data(stream_id, chunk)
            self.transport.write(self.conn.data_to_send())

            if body:
                # we have data left to send
                future = self.flow_control_futures[stream_id] = asyncio.Future(loop=self.loop)
                yield from future
            else:
                break

    @asyncio.coroutine
    def _send_request(self, stream_id, headers, body):
        self.conn.send_headers(stream_id, headers)

        future = asyncio.Future(loop=self.loop)
        self.response_futures[stream_id] = future

        if body is not None:
            yield from self._send_request_body(stream_id, body)
        self.conn.end_stream(stream_id)

        self.transport.write(self.conn.data_to_send())

        return (yield from future)

    def handle_response(self, stream_id):
        future = self.response_futures.pop(stream_id)
        response_event = self.events_queue[stream_id].popleft()
        data_event = None
        while True:
            data = self.events_queue[stream_id].popleft()
            if isinstance(data, DataReceived):
                data_event = data
            elif isinstance(data, StreamEnded):
                break
        self.events_queue.pop(stream_id)

        headers = dict(response_event.headers)
        data = data_event.data if data_event is not None else None
        status_code = int(headers[":status"])
        if status_code != 200:
            error = HTTP2Error(status_code, headers, data)
            future.set_exception(error)
        else:
            future.set_result((headers, data))


def prepare_request(method: HTTPMethod, parsed_url):
    request_headers = [
        (':method', method.value),
        (':authority', parsed_url.hostname),
        (':scheme', parsed_url.scheme),
        (':path', parsed_url.path),
    ]
    return request_headers


@asyncio.coroutine
def request(method: HTTPMethod, url: str, *, loop=None):
    parsed_url = urlsplit(url)
    headers = prepare_request(method, parsed_url)
    conn = yield from H2ClientProtocol.connect(parsed_url.hostname, 443, loop=loop)
    return (yield from conn.send_request(headers))


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    req = request(HTTPMethod.GET, "https://http2bin.org/get", loop=loop)
    headers, data = loop.run_until_complete(req)
    print(data.decode())
    loop.close()

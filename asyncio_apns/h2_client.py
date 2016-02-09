import asyncio
import enum
import ssl
import collections
from urllib.parse import urlsplit

from h2.connection import H2Connection
from h2.events import (ConnectionTerminated, DataReceived,
                       ResponseReceived, StreamEnded)


class HTTPMethod(enum.Enum):
    GET = "GET"
    POST = "POST"


class HTTP2Error(Exception):
    def __init__(self, code, headers, data=None):
        self.code = code
        self.headers = headers
        self.data = data


class DisconnectError(Exception):
    def __init__(self, code, data=None):
        self.code = code
        self.data = data


class H2ClientProtocol(asyncio.Protocol):
    def __init__(self, connection=H2Connection()):
        self.conn = connection
        self.response_futures = collections.deque()
        self.events_queue = collections.defaultdict(collections.deque)  # stream_id -> deque
        self.transport = None

    @classmethod
    @asyncio.coroutine
    def connect(cls, host: str, port: int,
                *, cert_file=None, key_file=None, loop=None):
        if loop is None:
            loop = asyncio.get_event_loop()
        ssl_context = ssl.create_default_context()
        ssl_context.set_alpn_protocols(["h2"])
        if cert_file and key_file:
            ssl_context.load_cert_chain(cert_file, key_file)
        # waiting for successful connect
        _, protocol = yield from loop.create_connection(H2ClientProtocol, host=host, port=port, ssl=ssl_context)
        return protocol

    def connection_made(self, transport):
        self.transport = transport
        self.conn.initiate_connection()
        self.transport.write(self.conn.data_to_send())

    def connection_lost(self, exc):
        pass

    def data_received(self, data):
        events = self.conn.receive_data(data)
        self.transport.write(self.conn.data_to_send())
        for event in events:
            if isinstance(event, ResponseReceived) or isinstance(event, DataReceived):
                self.events_queue[event.stream_id].append(event)
            elif isinstance(event, StreamEnded):
                self.events_queue[event.stream_id].append(event)
                self.handle_response(event.stream_id)
            elif isinstance(event, ConnectionTerminated):
                self.on_terminated(event.error_code, event.additional_data)

        data = self.conn.data_to_send()
        if data:
            self.transport.write(data)

    def on_terminated(self, error_code, data):
        while self.response_futures:
            f = self.response_futures.popleft()
            f.set_exception(DisconnectError(error_code, data))

    def send_request(self, headers, body=None):
        stream_id = 1
        self.conn.send_headers(stream_id, headers)
        if body is not None:
            self.conn.send_data(stream_id, body)
        self.conn.end_stream(stream_id)
        future = asyncio.Future()
        self.response_futures.append(future)
        return future

    def handle_response(self, stream_id):
        future = self.response_futures.popleft()
        response_event = self.events_queue[stream_id].popleft()
        data_event = None
        while True:
            data = self.events_queue[stream_id].popleft()
            if isinstance(data, DataReceived):
                data_event = data
            elif isinstance(data, StreamEnded):
                break

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

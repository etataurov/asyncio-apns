import asyncio
import json
import enum
from typing import Union
from .errors import APNsError, APNsDisconnectError
from .h2_client import H2ClientProtocol, HTTP2Error, HTTPMethod, DisconnectError
from .payload import Payload


class NotificationPriority(enum.Enum):
	Immediate = 10
	Delayed = 5


@asyncio.coroutine
def connect(cert_file: str, key_file: str, *, development=False, loop=None, production_server="api.push.apple.com", development_server="api.development.push.apple.com", port_server=443):
    connection = APNsConnection(cert_file, key_file, development=development, loop=loop, production_server=production_server, development_server=development_server, port_server=port_server)
    yield from connection.connect()
    return connection


def _get_apns_id(headers: dict):
    return headers.get("apns-id")


class APNsConnection:
    def __init__(self, cert_file: str, key_file: str, *, development=False, loop=None, production_server="api.push.apple.com", development_server="api.development.push.apple.com", port_server=443):
        self.protocol = None
        self.cert_file = cert_file
        self.key_file = key_file
        self.development = development
        self._loop = loop
        self.production_server = production_server
        self.development_server = development_server
        self.port_server = port_server
        self._connection_coro = None

    @property
    def connected(self):
        return self.protocol is not None and self.protocol.connected

    @asyncio.coroutine
    def _do_connect(self):
        host = self.development_server if self.development else self.production_server
        self.protocol = yield from H2ClientProtocol.connect(
                host, self.port_server, cert_file=self.cert_file,
                key_file=self.key_file, loop=self._loop)

    @asyncio.coroutine
    def connect(self):
        if self.connected:
            return
        if self._connection_coro:
            yield from self._connection_coro
            return
        try:
            self._connection_coro = self._do_connect()
            yield from self._connection_coro
        finally:
            self._connection_coro = None

    def disconnect(self):
        self.protocol.disconnect()
        self.protocol = None

    def _prepare_request(self, payload: Union[Payload, str], token: str):
        if not isinstance(payload, Payload):
            payload = Payload(payload)
        data = json.dumps(payload.as_dict()).encode()
        request_headers = [
            (':method', HTTPMethod.POST.value),
            (':scheme', 'https'),
            (':path', "/3/device/{}".format(token)),
            ('content-length', str(len(data)))
        ]
        return request_headers, data

    @asyncio.coroutine
    def send_message(self, payload: Union[Payload, str], token: str, prioriy=NotificationPriority.Immediate, topic=None):
        if not self.connected:
            yield from self.connect()
        headers, data = self._prepare_request(payload, token)
        headers.append(("apns-priority", str(prioriy.value)))
        if topic:
            headers.append(("apns-topic", topic))
        try:
            headers, _ = yield from self.protocol.send_request(headers, data)
            return _get_apns_id(headers)
        except HTTP2Error as exc:
            error_data = exc.json_data()
            reason = None
            if error_data is not None:
                reason = error_data.get("reason")
            raise APNsError(reason, _get_apns_id(exc.headers))
        except DisconnectError as exc:
            error_data = exc.json_data()
            reason = None
            if error_data is not None:
                reason = error_data.get("reason")
            raise APNsDisconnectError(reason)

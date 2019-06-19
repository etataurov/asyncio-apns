import asyncio
import json
import enum
from typing import Union
from .errors import APNsError, APNsDisconnectError
from .h2_client import H2ClientProtocol, HTTP2Error, HTTPMethod, DisconnectError
from .payload import Payload


PRODUCTION_SERVER_ADDR = "api.push.apple.com"
DEVELOPMENT_SERVER_ADDR = "api.development.push.apple.com"


class NotificationPriority(enum.IntEnum):
    immediate = 10
    delayed = 5


@asyncio.coroutine
def connect(cert_file: str, key_file: str, *, development=False, loop=None):
    server_addr = DEVELOPMENT_SERVER_ADDR if development else PRODUCTION_SERVER_ADDR
    connection = APNsConnection(cert_file, key_file, server_addr=server_addr, loop=loop)
    yield from connection.connect()
    return connection


def _get_apns_id(headers: dict):
    return headers.get("apns-id")


class APNsConnection:
    def __init__(self, cert_file: str, key_file: str, *, loop=None,
                 server_addr=PRODUCTION_SERVER_ADDR, server_port=443):
        self.protocol = None
        self.cert_file = cert_file
        self.key_file = key_file
        self.server_addr = server_addr
        self.server_port = server_port
        self._loop = loop
        self._connection_task = None

    @property
    def connected(self):
        return self.protocol is not None and self.protocol.connected

    @asyncio.coroutine
    def _do_connect(self):
        verify_ssl = self.server_addr in (PRODUCTION_SERVER_ADDR, DEVELOPMENT_SERVER_ADDR)
        self.protocol = yield from H2ClientProtocol.connect(
                self.server_addr, self.server_port, cert_file=self.cert_file,
                key_file=self.key_file, verify_ssl=verify_ssl, loop=self._loop)

    @asyncio.coroutine
    def connect(self):
        if self.connected:
            return
        if self._connection_task:
            yield from self._connection_task
            return
        try:
            self._connection_task = self._loop.create_task(self._do_connect())
            yield from self._connection_task
        finally:
            self._connection_task = None

    def disconnect(self):
        self.protocol.disconnect()
        self.protocol = None

    def _prepare_request(self, payload: Union[Payload, str], token: str,
                         priority: NotificationPriority, topic: str):
        if not isinstance(payload, Payload):
            payload = Payload(payload)
        data = json.dumps(payload.as_dict()).encode()
        request_headers = [
            (':method', HTTPMethod.POST.value),
            (':authority', self.server_addr),
            (':scheme', 'https'),
            (':path', "/3/device/{}".format(token)),
            ('content-length', str(len(data))),
            ('apns-priority', str(priority.value))
        ]
        if topic:
            request_headers.append(('apns-topic', topic))
        return request_headers, data

    @asyncio.coroutine
    def send_message(self, payload: Union[Payload, str], token: str,
                     priority: NotificationPriority = NotificationPriority.immediate,
                     topic: str = None):
        if not self.connected:
            yield from self.connect()
        headers, data = self._prepare_request(payload, token, priority, topic)
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

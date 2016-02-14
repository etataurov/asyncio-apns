import asyncio
import json
from .errors import APNsError, APNsDisconnectError
from .h2_client import H2ClientProtocol, HTTP2Error, HTTPMethod, DisconnectError


PRODUCTION_SERVER_ADDR = 'gateway.push.apple.com'
DEVELOPMENT_SERVER_ADDR = "api.push.apple.com"


@asyncio.coroutine
def connect(cert_file: str, key_file: str, *, development=False, loop=None):
    connection = APNsConnection(cert_file, key_file, development=development, loop=loop)
    yield from connection.connect()
    return connection


def _get_apns_id(headers: dict):
    return headers.get("apns-id")


class APNsConnection:
    def __init__(self, cert_file: str, key_file: str, *, development=False, loop=None):
        self.protocol = None
        self.cert_file = cert_file
        self.key_file = key_file
        self.development = development
        self._loop = loop

    @asyncio.coroutine
    def connect(self):
        host = DEVELOPMENT_SERVER_ADDR if self.development else PRODUCTION_SERVER_ADDR
        self.protocol = yield from H2ClientProtocol.connect(
                host, 443, cert_file=self.cert_file,
                key_file=self.key_file, loop=self._loop)

    def _prepare_request(self, payload, token):
        data = json.dumps(payload.as_dict()).encode()
        request_headers = [
            (':method', HTTPMethod.POST.value),
            (':scheme', 'https'),
            (':path', "/3/device/{}".format(token)),
            ('content-length', str(len(data)))
        ]
        return request_headers, data

    @asyncio.coroutine
    def send_message(self, payload, token):
        headers, data = self._prepare_request(payload, token)
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

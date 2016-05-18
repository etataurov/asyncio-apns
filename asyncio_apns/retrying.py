import asyncio

from .apns_connection import APNsConnection
from .errors import APNsDisconnectError


class RetryingProxy:
    def __init__(self, client: APNsConnection, *, loop=None):
        self.client = client
        self._loop = loop or asyncio.get_event_loop()

    def __getattr__(self, item):
        return getattr(self.client, item)

    @asyncio.coroutine
    def send_message(self, *args, resend_timeout=0.5, **kwargs):
        while True:
            try:
                yield from self.client.send_message(*args, **kwargs)
                break
            except APNsDisconnectError:
                yield from asyncio.sleep(resend_timeout, loop=self._loop)
                resend_timeout *= 2

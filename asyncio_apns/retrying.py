import asyncio

from .apns import ApnsClient
from .errors import ApnsDisconnectError, ApnsError


class RetryingProxy:
    def __init__(self, client: ApnsClient, *, loop=None):
        self.client = client
        self._loop = loop

    def __getattr__(self, item):
        return getattr(self.client, item)

    @asyncio.coroutine
    def send_message(self, *args, resend_timeout=0.5, **kwargs):
        loop = self._loop or asyncio.get_event_loop()
        while True:
            try:
                yield from self.client.send_message(*args, **kwargs)
                break
            except ApnsDisconnectError:
                yield from loop.sleep(resend_timeout)
                resend_timeout *= 2
            except ApnsError as exc:
                if exc.message_was_sent():
                    break
                raise

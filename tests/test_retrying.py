import asyncio
from unittest import mock
import pytest

from asyncio_apns.errors import APNsError, APNsDisconnectError
from asyncio_apns.retrying import RetryingProxy


@pytest.mark.asyncio
def test_retrying_success(event_loop):
    client = mock.MagicMock()
    proxy = RetryingProxy(client, loop=event_loop)
    future = asyncio.Future(loop=event_loop)
    client.send_message.side_effect = lambda *args, **kwargs: future
    args = ("some_message", "some_token")
    res = proxy.send_message(*args)
    future.set_result(None)
    yield from res
    client.send_message.assert_called_once_with(*args)


@pytest.mark.asyncio
def test_retrying_with_error(event_loop):
    client = mock.MagicMock()
    proxy = RetryingProxy(client, loop=event_loop)
    future = asyncio.Future(loop=event_loop)
    client.send_message.side_effect = lambda *args, **kwargs: future
    args = ("some_message", "some_token")
    message_id = 1
    kwargs = dict(message_id=message_id)
    res = proxy.send_message(*args, **kwargs)
    exception = APNsError(2, message_id)
    future.set_exception(exception)
    with pytest.raises(APNsError) as excinfo:
        yield from res
    assert excinfo.value is exception
    client.send_message.assert_called_once_with(*args, **kwargs)

# TODO test APNsDisconnectError

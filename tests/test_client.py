import asyncio
from unittest import mock
import pytest

from asyncio_apns.apns import ErrorWaiter, ApnsError


@pytest.mark.asyncio
def test_waiter_ok(event_loop):
    conn = mock.MagicMock()
    waiter = ErrorWaiter(conn, loop=event_loop)
    read_future = asyncio.Future(loop=event_loop)
    conn.read_by_format.side_effect = lambda _: read_future
    waiter.start_waiting()
    try:
        res = yield from waiter.expect(1, timeout=1)
    finally:
        waiter.stop()

@pytest.mark.asyncio
def test_waiter_with_error(event_loop):
    conn = mock.MagicMock()
    waiter = ErrorWaiter(conn, loop=event_loop)
    read_future = asyncio.Future(loop=event_loop)
    conn.read_by_format.side_effect = lambda _: read_future
    waiter.start_waiting()
    message_id = 1
    waiter_future = waiter.expect(message_id, timeout=1)
    error_status = 2
    read_future.set_result((8, error_status, message_id))
    with pytest.raises(ApnsError) as excinfo:
        yield from waiter_future
    assert excinfo.value.status == error_status


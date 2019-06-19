import asyncio
import functools
from unittest import mock
import sys

import pytest

from h2.events import WindowUpdated, ResponseReceived, StreamEnded, ConnectionTerminated
from h2.exceptions import TooManyStreamsError
from asyncio_apns.h2_client import H2ClientProtocol, HTTP2Error, DisconnectError


@pytest.fixture
def apns_response():
    def make_response(stream_id=1, status=200):
        response = ResponseReceived()
        response.stream_id = stream_id
        response.headers = [(":status", status)]
        ended = StreamEnded()
        ended.stream_id = stream_id
        return [response, ended]
    return make_response


def test_init():
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    assert protocol.conn is conn


def test_connected():
    protocol = H2ClientProtocol()
    assert not protocol.connected
    protocol.connection_made(mock.MagicMock())
    assert protocol.connected
    protocol.connection_lost(Exception())
    assert not protocol.connected


def test_connection_made():
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    data = b'some_data'
    conn.data_to_send.return_value = data
    protocol.connection_made(transport)
    conn.initiate_connection.assert_called_once_with()
    transport.write.assert_called_once_with(data)


@pytest.mark.asyncio
def test_future_done(apns_response, event_loop):
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    future = asyncio.ensure_future(protocol._send_request(1, [], body=None))
    conn.receive_data.return_value = apns_response(stream_id=1)
    event_loop.call_soon(functools.partial(protocol.data_received, b'some_data'))

    yield from future
    assert future.done()


@pytest.mark.asyncio
def test_future_exception(apns_response, event_loop):
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    conn.get_next_available_stream_id.return_value = 1
    future = asyncio.ensure_future(protocol._send_request(1, [], body=None))
    conn.receive_data.return_value = apns_response(stream_id=1, status=404)
    event_loop.call_soon(functools.partial(protocol.data_received, b'some_data'))

    with pytest.raises(HTTP2Error):
        yield from future

    assert future.exception().code == 404


@pytest.mark.asyncio
def test_future_exception_on_disconnect(event_loop):
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    future = asyncio.ensure_future(protocol._send_request(1, [], body=None))
    conn.receive_data.return_value = [ConnectionTerminated()]
    event_loop.call_soon(functools.partial(protocol.data_received, b'some_data'))

    with pytest.raises(DisconnectError):
        yield from future


@pytest.mark.asyncio
def test_future_on_connection_lost(event_loop):
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    future = asyncio.ensure_future(protocol._send_request(1, [], body=None))
    event_loop.call_soon(functools.partial(protocol.connection_lost, Exception()))

    with pytest.raises(DisconnectError):
        yield from future


@pytest.mark.asyncio
def test_response_order(apns_response, event_loop):
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    future1 = asyncio.ensure_future(protocol._send_request(1, [], body=None))
    future2 = asyncio.ensure_future(protocol._send_request(2, [], body=None))
    conn.receive_data.return_value = apns_response(stream_id=2)
    event_loop.call_soon(functools.partial(protocol.data_received, b'some_data'))

    yield from future2
    assert not future1.done()
    future1.cancel()


@pytest.mark.asyncio
@asyncio.coroutine
def test_too_many_streams_handled(apns_response):
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    conn.send_headers.side_effect = TooManyStreamsError
    conn.get_next_available_stream_id.return_value = 1
    future = asyncio.ensure_future(protocol.send_request([]))
    yield from asyncio.sleep(0)
    assert not future.done()
    conn.send_headers.reset_mock()
    conn.send_headers.side_effect = None
    protocol._on_stream_closed()
    yield from asyncio.sleep(0)
    conn.receive_data.return_value = apns_response(stream_id=1)
    protocol.data_received(b'some_data')
    yield from asyncio.sleep(0)
    assert future.done()
    assert conn.send_headers.called


@pytest.mark.asyncio
@asyncio.coroutine
def test_too_many_streams_on_terminated():
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    conn.send_headers.side_effect = TooManyStreamsError
    conn.get_next_available_stream_id.return_value = 1
    future = asyncio.ensure_future(protocol.send_request([]))
    yield from asyncio.sleep(0)
    protocol.connection_lost(Exception())
    yield from asyncio.sleep(0)

    with pytest.raises(DisconnectError):
        future.result()


@pytest.mark.asyncio
def test_request_with_body(apns_response, event_loop):
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    conn.local_flow_control_window.return_value = sys.maxsize
    conn.max_outbound_frame_size = sys.maxsize

    future = asyncio.ensure_future(protocol._send_request(1, [], body=b'foobarbody'))
    conn.receive_data.return_value = apns_response(stream_id=1)
    event_loop.call_soon(
        functools.partial(protocol.data_received, b'some_data'))

    yield from future
    assert future.done()


@pytest.mark.asyncio
def test_request_with_body_chunks(apns_response, event_loop):
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    body = b'a' * 100
    conn.local_flow_control_window.return_value = sys.maxsize
    conn.max_outbound_frame_size = len(body) // 9

    future = asyncio.ensure_future(protocol._send_request(1, [], body=body))
    conn.receive_data.return_value = apns_response(stream_id=1)
    event_loop.call_soon(
        functools.partial(protocol.data_received, b'some_data'))

    yield from future
    assert future.done()
    calls = [mock.call(1, b'a'*11) for _ in range(len(body) // conn.max_outbound_frame_size)] + [mock.call(1, b'a')]
    conn.send_data.assert_has_calls(calls)


@pytest.mark.parametrize("opened_for_stream", [True, False])
@pytest.mark.asyncio
@asyncio.coroutine
def test_request_with_body_window_limit(apns_response, event_loop, opened_for_stream):
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)
    stream_id = 1

    body = b'a' * 100
    conn.local_flow_control_window.return_value = len(body) // 2
    conn.max_outbound_frame_size = len(body) // 9

    future = asyncio.ensure_future(protocol._send_request(stream_id, [], body=body))
    yield from asyncio.sleep(0)
    assert stream_id in protocol.flow_control_futures
    assert not future.done()

    event = WindowUpdated()
    if opened_for_stream:
        event.stream_id = stream_id
    conn.receive_data.return_value = [event]
    protocol.data_received(b'')

    conn.receive_data.return_value = apns_response(stream_id=stream_id)
    event_loop.call_soon(
        functools.partial(protocol.data_received, b'some_data'))

    yield from future
    assert future.done()
    assert not protocol.flow_control_futures

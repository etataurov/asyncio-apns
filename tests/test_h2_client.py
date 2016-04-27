import asyncio
from unittest import mock
import pytest

from h2.exceptions import TooManyStreamsError
from asyncio_apns.h2_client import *


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


def test_future_done(apns_response):
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    future = protocol._send_request(1, [], body=None)
    conn.receive_data.return_value = apns_response(stream_id=1)
    protocol.data_received(b'some_data')

    assert future.done()


def test_future_exception(apns_response):
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    conn.get_next_available_stream_id.return_value = 1
    future = protocol._send_request(1, [], body=None)
    conn.receive_data.return_value = apns_response(stream_id=1, status=404)
    protocol.data_received(b'some_data')

    with pytest.raises(HTTP2Error):
        future.result()

    assert future.exception().code == 404


def test_future_exception_on_disconnect():
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    future = protocol._send_request(1, [], body=None)
    conn.receive_data.return_value = [ConnectionTerminated()]
    protocol.data_received(b'some_data')

    with pytest.raises(DisconnectError):
        future.result()


def test_future_on_connection_lost():
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    future = protocol._send_request(1, [], body=None)
    protocol.connection_lost(Exception())

    with pytest.raises(DisconnectError):
        future.result()


def test_response_order(apns_response):
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    future1 = protocol._send_request(1, [], body=None)
    future2 = protocol._send_request(2, [], body=None)
    conn.receive_data.return_value = apns_response(stream_id=2)
    protocol.data_received(b'some_data')
    assert not future1.done()
    assert future2.done()


@pytest.mark.asyncio
def test_too_many_streams_handled(apns_response):
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    conn.send_headers.side_effect = TooManyStreamsError
    conn.get_next_available_stream_id.return_value = 1
    future = asyncio.async(protocol.send_request([]))
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
def test_too_many_streams_on_terminated():
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    conn.send_headers.side_effect = TooManyStreamsError
    conn.get_next_available_stream_id.return_value = 1
    future = asyncio.async(protocol.send_request([]))
    yield from asyncio.sleep(0)
    protocol.connection_lost(Exception())
    yield from asyncio.sleep(0)

    with pytest.raises(DisconnectError):
        future.result()

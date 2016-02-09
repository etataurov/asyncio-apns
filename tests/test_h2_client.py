from unittest import mock
import pytest

from asyncio_apns.h2_client import *


def test_init():
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    assert protocol.conn is conn


def test_connection_made():
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    data = b'some_data'
    conn.data_to_send.return_value = data
    protocol.connection_made(transport)
    conn.initiate_connection.assert_called_once_with()
    transport.write.assert_called_once_with(data)


def test_future_done():
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    future = protocol.send_request([])
    resp = ResponseReceived()
    resp.headers = [(":status", 200)]
    conn.receive_data.return_value = [resp, StreamEnded()]
    protocol.data_received(b'some_data')

    assert future.done()


def test_future_exception():
    conn = mock.MagicMock()
    protocol = H2ClientProtocol(conn)
    transport = mock.MagicMock()
    protocol.connection_made(transport)

    future = protocol.send_request([])
    resp = ResponseReceived()
    resp.headers = [(":status", 404)]
    conn.receive_data.return_value = [resp, StreamEnded()]
    protocol.data_received(b'some_data')

    with pytest.raises(HTTP2Error):
        future.result()

    assert future.exception().code == 404



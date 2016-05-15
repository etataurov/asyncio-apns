import asyncio
from unittest import mock
import json

import pytest

from asyncio_apns import APNsConnection, Payload, connect


def future_with_result(result):
    f = asyncio.Future()
    f.set_result(result)
    return f


@pytest.yield_fixture
def apns_connect():
    patcher = mock.patch("asyncio_apns.apns_connection.H2ClientProtocol")
    mock_protocol = patcher.start()

    @asyncio.coroutine
    def connector():
        mock_protocol.connect.return_value = future_with_result(mock.MagicMock())
        connection = yield from connect("some.crt", "some.key")
        return connection
    yield connector
    patcher.stop()


def test_initial():
    connection = APNsConnection("some.crt", "some.key")
    assert not connection.connected


@pytest.mark.asyncio
def test_connect(apns_connect):
    connection = yield from apns_connect()
    assert connection.connected


@pytest.mark.asyncio
def test_disconnect(apns_connect):
    connection = yield from apns_connect()
    connection.disconnect()
    assert not connection.connected


@pytest.mark.asyncio
def test_connect_twice():
    with mock.patch("asyncio_apns.apns_connection.H2ClientProtocol") as mock_protocol:
        future = asyncio.Future()
        mock_protocol.connect.return_value = future
        connection = APNsConnection("some.crt", "some.key")
        # scheduling first
        first = asyncio.async(connection.connect())
        yield from asyncio.sleep(0)
        assert connection._connection_coro is not None
        # creating second
        second = asyncio.async(connection.connect())
        yield from asyncio.sleep(0)
        future.set_result(mock.MagicMock())
        yield from second

        first.result()
        second.result()
        assert mock_protocol.connect.call_count == 1


@pytest.mark.asyncio
def test_connect_when_connected():
    with mock.patch("asyncio_apns.apns_connection.H2ClientProtocol") as mock_protocol:
        mock_protocol.connect.return_value = future_with_result(mock.MagicMock())
        connection = APNsConnection("some.crt", "some.key")
        yield from connection.connect()
        yield from connection.connect()
        assert mock_protocol.connect.call_count == 1


@pytest.mark.asyncio
def test_send_message(apns_connect):
    connection = yield from apns_connect()
    token = "abcde"
    message = "Hello"
    connection.protocol.send_request.return_value = future_with_result(
        (mock.MagicMock(), mock.MagicMock()))
    yield from connection.send_message(message, token)
    expected_request_body = json.dumps(Payload(message).as_dict()).encode()
    connection.protocol.send_request.assert_called_with(mock.ANY, expected_request_body)


@pytest.mark.asyncio
def test_not_connected_when_sending_message(apns_connect):
    connection = yield from apns_connect()
    connection.disconnect()
    from asyncio_apns import apns_connection
    apns_connection.H2ClientProtocol.connect.reset_mock()
    protocol_instance = apns_connection.H2ClientProtocol.connect.return_value.result()
    token = "abcde"
    message = "Hello"
    protocol_instance.send_request.return_value = future_with_result(
        (mock.MagicMock(), mock.MagicMock()))
    yield from connection.send_message(message, token)
    assert apns_connection.H2ClientProtocol.connect.called

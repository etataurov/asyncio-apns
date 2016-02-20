import asyncio
from unittest import mock
import json

import pytest

from asyncio_apns import APNsConnection, Payload


def future_with_result(result):
    f = asyncio.Future()
    f.set_result(result)
    return f


@pytest.yield_fixture
def connect():
    patcher = mock.patch("asyncio_apns.apns_connection.H2ClientProtocol")
    mock_protocol = patcher.start()

    @asyncio.coroutine
    def connector():
        mock_protocol.connect.return_value = future_with_result(mock.MagicMock())
        connection = APNsConnection("some.crt", "some.key")
        yield from connection.connect()
        return connection
    yield connector
    patcher.stop()


def test_initial():
    connection = APNsConnection("some.crt", "some.key")
    assert not connection.connected


@pytest.mark.asyncio
def test_connect(connect):
    connection = yield from connect()
    assert connection.connected


@pytest.mark.asyncio
def test_send_message(connect):
    connection = yield from connect()
    token = "abcde"
    message = "Hello"
    connection.protocol.send_request.return_value = future_with_result(
        (mock.MagicMock(), mock.MagicMock()))
    yield from connection.send_message(message, token)
    expected_request_body = json.dumps(Payload(message).as_dict()).encode()
    connection.protocol.send_request.assert_called_with(mock.ANY, expected_request_body)

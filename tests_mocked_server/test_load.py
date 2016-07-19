import asyncio
import os
import subprocess
import time

import pytest
from asyncio_apns import APNsConnection, APNsError

CWD = os.path.dirname(os.path.realpath(__file__))


@pytest.yield_fixture(scope="module")
def mock_server(request):
    server = subprocess.Popen("./go-apns-server", shell=True, cwd=CWD)
    time.sleep(0.5)
    yield server
    server.terminate()


@pytest.mark.asyncio
def test_batch_send_messages(event_loop, mock_server):
    connection = APNsConnection(os.path.join(CWD, "cert.pem"), os.path.join(CWD, "key.pem"),
                                loop=event_loop, server_addr="127.0.0.1", server_port=8443)
    yield from connection.connect()

    @asyncio.coroutine
    def send_message():
        token = "fsd76fh23jhd6s2j2h"
        message = "Hello my world"
        try:
            yield from connection.send_message(message, token=token)
        except APNsError as exc:
            assert exc.status in ("BadDeviceToken", "Unregistered")

    tasks = []
    for _ in range(1000):
        tasks.append(asyncio.async(send_message(), loop=event_loop))
    yield from asyncio.wait(tasks, loop=event_loop)
    connection.disconnect()

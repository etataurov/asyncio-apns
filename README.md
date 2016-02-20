# asyncio-apns

[![Build Status](https://travis-ci.org/etataurov/asyncio-apns.svg?branch=develop)](https://travis-ci.org/etataurov/asyncio-apns)
[![Coverage Status](https://coveralls.io/repos/github/etataurov/asyncio-apns/badge.svg?branch=develop)](https://coveralls.io/github/etataurov/asyncio-apns?branch=develop)

asyncio client for Apple Push Notification Service

Work in progress

## Usage

```python
import asyncio

from asyncio_apns import connect

CERT_FILE = 'path/to/cert_file'
KEY_FILE = 'path/to/key_file'

async def send_push(message, token, loop):
    apns = await connect(CERT_FILE, KEY_FILE, loop=loop)
    await apns.send_message(message, token)
    apns.disconnect()

message = 'Hello World!'
token = 'YOUR_DEVICE_TOKEN'

loop = asyncio.get_event_loop()
loop.run_until_complete(send_push(message, token, loop))
loop.close()
```

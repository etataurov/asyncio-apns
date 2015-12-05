import asyncio
import struct


class Connection:
    def __init__(self, reader, writer, *, loop=None):
        self.reader = reader
        self.writer = writer
        self._loop = loop
        self._closed = False

    @property
    def closed(self) -> bool:
        return (self._closed or self.reader.at_eof() or
                self.reader.exception() is not None)

    def close(self):
        self._closed = True
        self.writer.close()
        self.writer = None
        self.reader = None

    @asyncio.coroutine
    def read_by_format(self, format: str) -> bytes:
        try:
            data = yield from self.reader.readexactly(struct.calcsize(format))
            data = struct.unpack(format, data)
        except asyncio.IncompleteReadError:
            data = None
        return data

    def write(self, data: bytes):
        self.writer.write(data)

    def drain(self):
        return self.writer.drain()

__all__ = ["Connection"]

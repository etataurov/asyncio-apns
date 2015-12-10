"""
APNs protocol related methods & constants

https://developer.apple.com/library/ios/
documentation/NetworkingInternet/Conceptual/RemoteNotificationsPG/Chapters/
CommunicatingWIthAPS.html#//apple_ref/doc/uid/TP40008194-CH101-SW4
"""
import struct
from binascii import unhexlify

ERROR_FORMAT = "!BBI"

FEEDBACK_HEADER_FORMAT = "!LH"


def token_format(token_length):
    return '{}s'.format(token_length)


def pack_frame(token_hex, payload, identifier, expiration, priority):
    """
    copy-paste from https://github.com/jleclanche/django-push-notifications/blob/master/push_notifications/apns.py
    """
    token = unhexlify(token_hex)
    # |COMMAND|FRAME-LEN|{token}|{payload}|{id:4}|{expiration:4}|{priority:1}
    frame_len = 3 * 5 + len(token) + len(payload) + 4 + 4 + 1  # 5 items, each 3 bytes prefix, then each item length
    frame_fmt = "!BIBH%ssBH%ssBHIBHIBHB" % (len(token), len(payload))
    frame = struct.pack(
        frame_fmt,
        2, frame_len,
        1, len(token), token,
        2, len(payload), payload,
        3, 4, identifier,
        4, 4, expiration,
        5, 1, priority)
    return frame

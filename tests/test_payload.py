from asyncio_apns import Payload


def test_payload():
    p = Payload()
    assert p.alert is None
    assert p.badge is None
    assert isinstance(p.as_dict(), dict)


def test_payload_with_alert():
    p = Payload(alert="XoXo")
    d = p.as_dict()
    assert d == {'aps': {'alert': "XoXo"}}
    aps_d = d['aps']
    assert aps_d['alert'] == "XoXo"


def test_payload_with_badge():
    p = Payload(badge=5)
    aps_d = p.as_dict()['aps']
    assert aps_d['badge'] == 5


def test_payload_with_sound():
    p = Payload(sound='default')
    aps_d = p.as_dict()['aps']
    assert aps_d['sound'] == 'default'


def test_payload_with_content_available():
    p = Payload(content_available=True)
    aps_d = p.as_dict()['aps']
    assert aps_d['content-available'] == 1

def test_payload_no_content_available():
    p = Payload(content_available=False)
    aps_d = p.as_dict()['aps']
    assert 'content-available' not in aps_d

def test_payload_with_category():
    p = Payload(category='some')
    aps_d = p.as_dict()['aps']
    assert aps_d['category'] == 'some'


def test_payload_with_custom_fields():
    p = Payload(custom={'1': 1, '2': '2'})
    d = p.as_dict()
    assert d['1'] == 1
    assert d['2'] == '2'


def test_payload_complete():
    p = Payload(alert='alert', badge=3,
                sound='terrible', content_available=True,
                category='category', custom={"hello": {"my": "friend"}})
    d = p.as_dict()
    assert d == {'hello': {'my': 'friend'},
                 'aps': {
                     'badge': 3, 'category': 'category',
                     'content-available': 1, 'alert': 'alert',
                     'sound': 'terrible'}}

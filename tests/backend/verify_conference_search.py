"""Public-directory filters with disposable native fixtures and in-memory email only."""
import uuid
from datetime import datetime, timedelta

from flask import session
from pytz import UTC, timezone

from indico.core.config import config
from indico.core.db import db
from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.auth import Identity
from indico.modules.events import Event
from indico.modules.events.layout import layout_settings
from indico.modules.events.models.events import EventType
from indico.modules.events.operations import create_event
from indico.modules.events.util import track_location_changes
from indico.modules.categories import Category
from indico.modules.users import User
from indico.modules.users.operations import create_user
from indico.modules.rb.models.locations import Location
from indico.util.date_time import now_utc
from indico.web.flask.app import make_app
from yujian_site import YujianSitePlugin
from yujian_site.conference_metadata import SUBJECT_DOMAINS

app = make_app(config_override={'EMAIL_BACKEND': 'indico.vendor.django_mail.backends.locmem.EmailBackend',
                                'SMTP_USE_CELERY': False})
app.config.update(TESTING=True, REPL=True)
prefix = 'search-fixture-' + uuid.uuid4().hex[:12]
event_ids, user_id, location_id = [], None, None
city = prefix + '-城市'
legacy_city = prefix + '-旧场地'
hidden_city = prefix + '-不可见城市'
now = now_utc()
with app.app_context():
    base = config.BASE_URL


def get(**args):
    response = client.get('/api/conferences/', query_string=args)
    assert response.status_code == 200, (response.status_code, response.get_data(as_text=True)[:180])
    return response.json


try:
    with app.test_request_context(base_url=base):
        user = create_user(prefix + '@example.invalid', {'first_name': 'Search fixture', 'last_name': prefix},
                           Identity(provider='indico', identifier=prefix, password=uuid.uuid4().hex))
        db.session.flush()
        user_id = user.id
        session.set_session_user(user)
        category = Category.get(YujianSitePlugin.settings.get('category_id'))
        def fixture(label, start=None, end=None, subjects=('数学',), location=city, metadata_city=None, **flags):
            start = start or now + timedelta(days=10)
            event = create_event(category, EventType.conference, {
                'title': prefix + ' ' + label, 'description': 'Disposable search fixture',
                'start_dt': start, 'end_dt': end or start + timedelta(hours=1), 'timezone': 'Asia/Shanghai',
                'location_data': {'inheriting': False, 'venue_name': location, 'room_name': '', 'address': ''}})
            event_ids.append(event.id)
            event.protection_mode = ProtectionMode.public
            event.visibility = None
            YujianSitePlugin.event_settings.set_multi(event, {'published': True, 'conference_metadata': {
                'city': metadata_city if metadata_city is not None else location, 'subject_domains': list(subjects)}})
            if flags.get('draft'):
                YujianSitePlugin.event_settings.set(event, 'published', False)
            if flags.get('hidden'):
                layout_settings.set(event, 'is_searchable', False)
            if flags.get('protected'):
                event.protection_mode = ProtectionMode.protected
            if flags.get('invisible'):
                event.visibility = 0
            if flags.get('deleted'):
                event.is_deleted = True
            if flags.get('wrong_type'):
                event._type = EventType.lecture
            if flags.get('wrong_category'):
                event.category = Category.get(0)
            return event.id
        maths_ids = [fixture(f'maths-{index}') for index in range(14)]
        fixture('different-subject', subjects=('物理学与力学',))
        multi_id = fixture('multiple-subjects', subjects=('数学', '人工智能'), location=prefix + '-multi')
        legacy_id = fixture('legacy', location=legacy_city, metadata_city='', subjects=())
        padded_city = prefix + '-带空格场地'
        padded_id = fixture('legacy-padded', location='  ' + padded_city + '  ', metadata_city='')
        long_city = prefix + '-超长场地-' + '长'*220
        long_id = fixture('legacy-long', location=long_city, metadata_city='')
        linked_city = prefix + '-原生关联场地'
        linked_venue = Location(name=linked_city)
        db.session.add(linked_venue)
        db.session.flush()
        location_id = linked_venue.id
        linked_id = fixture('legacy-linked', location='', metadata_city='')
        with track_location_changes():
            Event.get(linked_id).own_venue = linked_venue
            db.session.flush()
        boundary = timezone('Asia/Shanghai').localize(datetime(2098, 3, 1, 0, 15)).astimezone(UTC)
        boundary_id = fixture('month-boundary', start=boundary, location=prefix + '-边界')
        overlap_id = fixture('overlap', start=boundary-timedelta(hours=1), end=boundary+timedelta(hours=1), location=prefix + '-跨月')
        upcoming_id = fixture('phase-upcoming', start=now+timedelta(days=2), location=prefix + '-状态')
        ongoing_id = fixture('phase-ongoing', start=now-timedelta(hours=1), end=now+timedelta(hours=1), location=prefix + '-状态')
        ended_id = fixture('phase-ended', start=now-timedelta(days=2), location=prefix + '-状态')
        literal_id = fixture(r'literal%_\value', location=prefix + '-特殊字符')
        for flag in ('draft', 'hidden', 'protected', 'invisible', 'deleted', 'wrong_type', 'wrong_category'):
            fixture('hidden-' + flag, start=UTC.localize(datetime(2198, 7, 1)), location=hidden_city,
                    **{flag: True})
        db.session.commit()
    client = app.test_client()
    result = get(q=prefix, city=city, subject='数学')
    assert result['total'] == 14, 'City and subject filters must apply before total and pagination'
    assert [event['id'] for event in result['events']] == sorted(maths_ids, reverse=True)[:12]
    assert result['has_more'] and result['page'] == 1
    page2 = get(q=prefix, city=city, subject='数学', page=2)
    assert [event['id'] for event in page2['events']] == sorted(maths_ids, reverse=True)[12:]
    assert not page2['has_more']
    assert get(q=prefix, subject='人工智能')['events'][0]['id'] == multi_id
    assert get(q=prefix, city=legacy_city)['events'][0]['id'] == legacy_id
    assert get(q=prefix, time='2098-03')['total'] == 1
    assert get(q=prefix, time='2098-03')['events'][0]['id'] == boundary_id
    assert get(q=prefix, time='2098-02')['events'][0]['id'] == overlap_id
    for value, expected in (('upcoming', upcoming_id), ('ongoing', ongoing_id), ('ended', ended_id)):
        selected = get(q=prefix + ' phase-', time=value)
        assert [event['id'] for event in selected['events']] == [expected]
    assert get(q=prefix, city=prefix + '-不存在')['total'] == 0
    assert get(q=prefix + ' literal%_' + chr(92))['events'][0]['id'] == literal_id
    assert get(q=prefix, city="' OR 1=1 --")['total'] == 0
    facets = get(q=prefix, city=city, subject='数学', time='2098-03', filters=1)['filters']
    assert facets == get(filters=1)['filters'], 'Facets are independent of selected filters and keyword'
    assert city in facets['cities'] and legacy_city in facets['cities']
    assert hidden_city not in facets['cities'] and '2198-07' not in facets['months']
    assert '2098-03' in facets['months'] and '2098-02' in facets['months']
    assert facets['months'] == sorted(set(facets['months']), reverse=True)
    assert facets['cities'] == sorted(set(facets['cities']))
    assert facets['subjects'] == list(SUBJECT_DOMAINS)
    for expected_city, expected_id in ((padded_city, padded_id), (long_city, long_id), (linked_city, linked_id)):
        assert expected_city in facets['cities'], 'Normalize every emitted legacy venue to a selectable city option'
        selected = get(q=prefix, city=expected_city)
        assert [event['id'] for event in selected['events']] == [expected_id], 'City facet options must round-trip'
    assert all(value == value.strip() for value in facets['cities'])
    assert 'filters' not in get(q=prefix)
    assert get(q=prefix + ' hidden-')['total'] == 0
    for args in ({'time': 'future'}, {'time': '0000-01'}, {'time': '9999-12'}, {'time': '2098-13'},
                 {'time': '2098-2'}, {'subject': 'unknown'}, {'city': 'x\n'},
                 {'city': 'x\x00'}, {'page': '0'}, {'page': str(2**31)}):
        response = client.get('/api/conferences/', query_string=args)
        assert response.status_code == 400, (args, response.status_code)
    print('conference search passed: SQL pagination, metadata/legacy city, multi-subject, Shanghai months, phases, public-only independent facets, literal search, validation')
finally:
    with app.test_request_context(base_url=base):
        db.session.rollback()
        for event_id in event_ids:
            event = Event.get(event_id)
            if event:
                event.is_deleted = True
        if user_id:
            User.get(user_id).is_deleted = True
        if location_id:
            Location.get(location_id).is_deleted = True
        db.session.commit()

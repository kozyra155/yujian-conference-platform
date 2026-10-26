"""Run with the Indico container Python; no database, mail or live events are touched."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

assert Path(__file__).with_name('yujian_site').joinpath('conference_metadata.py').exists(), 'Conference metadata feature is missing'
from yujian_site.conference_metadata import conference_phase, validate_metadata, parse_dates, SUBJECT_DOMAINS, PLANNED_INDEXING
from werkzeug.exceptions import BadRequest

metadata = {'organizer_name': '测试主办单位', 'organizer_phone': '+86 010-12345678',
            'country': '中国', 'province': '北京市', 'city': '北京市', 'detail_address': '待定',
            'subject_domains': ['数学', '人工智能'], 'planned_indexing': ['SCI', 'EI']}
assert validate_metadata(metadata, required=True) == metadata
assert validate_metadata({})['subject_domains'] == []
assert validate_metadata({})['organizer_name'] == ''
assert len(SUBJECT_DOMAINS) == 45
assert '历史学/文学/哲学' in SUBJECT_DOMAINS
assert len(PLANNED_INDEXING) == 17
for patch in ({'organizer_name': ''}, {'subject_domains': ['unknown']}, {'planned_indexing': 'SCI'},
              {'country': 'x\x00'}, {'organizer_phone': 'x' * 101}):
    try:
        validate_metadata(metadata | patch, required=True)
    except BadRequest:
        pass
    else:
        raise AssertionError(f'Invalid metadata accepted: {patch}')
now = datetime(2030, 1, 1, tzinfo=timezone.utc)
event = SimpleNamespace(start_dt=now, end_dt=now + timedelta(days=1))
assert conference_phase(event, now - timedelta(seconds=1)) == 'upcoming'
assert conference_phase(event, now) == 'ongoing'
assert conference_phase(event, event.end_dt) == 'ended'
assert parse_dates({'start': '2030-01-01T08:00', 'end': '2030-01-01T09:00'})[0] == now
for dates in ({'start': '2030-01-01T08:00', 'end': '2030-01-01T08:00'},
              {'start': '2030-01-01T08:00+08:00', 'end': '2030-01-01T09:00'}):
    try:
        parse_dates(dates)
    except BadRequest:
        pass
    else:
        raise AssertionError('Invalid dates accepted')
print('metadata selfcheck passed')

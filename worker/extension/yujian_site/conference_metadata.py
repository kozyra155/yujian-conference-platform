"""Conference details shared by creation, editing and public listings."""
from datetime import datetime, timezone as utc_timezone
from hashlib import sha256
import json

from babel import Locale
from flask import request
from markupsafe import escape
from pytz import UTC, timezone
from werkzeug.exceptions import BadRequest, Conflict

from indico.modules.events import Event
from indico.modules.events.operations import update_event
from indico.modules.events.timetable.util import get_top_level_entries
from indico.modules.events.util import track_location_changes, track_time_changes
from indico.util.countries import get_countries
from indico.util.string import html_to_plaintext

from . import YujianSitePlugin
from .site_content import _settings

SUBJECT_DOMAINS = (
    '数学', '物理学与力学', '航空航天科学', '地球科学', '生物学与生物工程', '医学与医学工程', '人工智能',
    '计算机科学与技术', '电子与通信技术', '信息科学与系统科学', '信息与系统科学相关工程与技术', '动力与电气工程', '能源科学', '环境及资源科学技术',
    '材料科学', '冶金工程', '机械工程', '矿山工程', '土木建筑工程', '水利工程', '交通运输工程',
    '经济学', '管理学', '艺术学', '体育科学', '教育学', '社会学', '光学/光学工程',
    '海洋科学与工程', '测绘科学', '纺织科学', '安全科学', '化学与化学工程', '农林学/农业工程', '畜牧/兽医科学',
    '食品科学', '核科学', '天文学', '药学与中医学', '心理学', '政治学', '法学',
    '历史学/文学/哲学', '民族宗教', '交叉学科')
PLANNED_INDEXING = ('SSCI', 'SCI', 'EI', 'CPCI', 'CNKI', 'A&HCI', 'Scopus', 'Inspec', 'IEEE Xplore',
                    'SCIE', 'Google Scholar', 'ESCI', 'CPCI-S', 'CPCI-SSH', '维普', '万方', '其它')
METADATA_FIELDS = {'organizer_name': 200, 'organizer_phone': 100, 'country': 100,
                   'province': 100, 'city': 100, 'detail_address': 500}


def validate_metadata(data, required=False):
    result = {}
    for key, limit in METADATA_FIELDS.items():
        value = data.get(key, '')
        if (not isinstance(value, str) or len(value.strip()) > limit or
                any(ord(char) < 32 for char in value) or (required and not value.strip())):
            raise BadRequest(f'{key}: required text, maximum {limit} characters.')
        result[key] = value.strip()
    for key, choices in (('subject_domains', SUBJECT_DOMAINS), ('planned_indexing', PLANNED_INDEXING)):
        values = data.get(key, [])
        if not isinstance(values, list) or len(values) > len(choices) or any(value not in choices for value in values):
            raise BadRequest(f'{key}: choose values from the available options.')
        result[key] = list(dict.fromkeys(values))
    return result


def parse_dates(data):
    dates = []
    for key in ('start', 'end'):
        try:
            value = data.get(key)
            if not isinstance(value, str) or len(value) > 32:
                raise ValueError()
            value = datetime.fromisoformat(value)
            if value.tzinfo is not None:
                raise ValueError()
            dates.append(timezone('Asia/Shanghai').localize(value).astimezone(UTC))
        except (ValueError, OverflowError):
            raise BadRequest('Invalid date. Use local Shanghai time.') from None
    if dates[1] <= dates[0]:
        raise BadRequest('End time must be after start time.')
    return dates


def conference_phase(event, now=None):
    now = now or datetime.now(utc_timezone.utc)
    return 'upcoming' if now < event.start_dt else 'ongoing' if now < event.end_dt else 'ended'


def get_metadata(event):
    saved = _settings(event).get('conference_metadata') or {}
    return {**{key: '' for key in METADATA_FIELDS}, 'subject_domains': [], 'planned_indexing': [], **saved}


def location_name(metadata):
    return ' · '.join(dict.fromkeys(metadata[key] for key in ('country', 'province', 'city') if metadata[key]))


def get_basic_payload(event):
    from .blueprint import serialize
    settings = _settings(event)
    metadata = get_metadata(event)
    metadata.update(organizer_name=html_to_plaintext(str(event.organizer_info or metadata['organizer_name']) or '<p></p>'),
                    organizer_phone=(event.contact_phones or [metadata['organizer_phone']])[0],
                    detail_address=event.address or metadata['detail_address'])
    basic = {**metadata, 'title': event.title,
             'start': event.start_dt.astimezone(timezone('Asia/Shanghai')).strftime('%Y-%m-%dT%H:%M'),
             'end': event.end_dt.astimezone(timezone('Asia/Shanghai')).strftime('%Y-%m-%dT%H:%M'),
             'description': html_to_plaintext(str(event.description) or '<p></p>')}
    # Native editors do not increment our counter; include their original values to detect stale drafts.
    snapshot = {'basic': basic, 'description_html': str(event.description),
                'organizer_html': str(event.organizer_info), 'phones': event.contact_phones,
                'start': event.start_dt.isoformat(), 'end': event.end_dt.isoformat(),
                'timezone': event.timezone, 'location': event.widget_location_data,
                'inherit_location': event.inherit_location}
    fingerprint = sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    return {'event': serialize(event, private=True), 'revision': settings.get('basic_revision', 0),
            'basic': basic, 'fingerprint': fingerprint}


def metadata_options():
    return {'subject_domains': SUBJECT_DOMAINS, 'planned_indexing': PLANNED_INDEXING,
            'countries': [{'value': name, 'label_en': get_countries(Locale.parse('en_GB')).get(code, name)}
                          for code, name in get_countries(Locale.parse('zh_CN')).items()]}


def register_routes(bp):
    from .blueprint import RHAccount, RHManaged, body, response, text

    class RHMetadataOptions(RHAccount):
        def _process(self):
            return response(metadata_options())

    class RHBasic(RHManaged):
        def _process(self):
            if request.method == 'GET':
                return response(get_basic_payload(self.event))
            data = body()
            if (set(data) != {'revision', 'fingerprint', 'basic'} or type(data.get('revision')) is not int or
                    not isinstance(data['basic'], dict) or not isinstance(data['fingerprint'], str) or
                    len(data['fingerprint']) != 64):
                raise BadRequest('Expected revision, fingerprint and basic information.')
            basic = data['basic']
            if set(basic) - (set(METADATA_FIELDS) | {'subject_domains', 'planned_indexing', 'title', 'start', 'end', 'description'}):
                raise BadRequest('Unknown basic information fields.')
            metadata = validate_metadata(basic, required=True)
            title, description = text(basic, 'title', 200), text(basic, 'description', 20000)
            start, end = parse_dates(basic)
            self.event = Event.query.filter_by(id=self.event.id).populate_existing().with_for_update().one()
            self._check_access()
            current = get_basic_payload(self.event)
            if data['revision'] != current['revision'] or data['fingerprint'] != current['fingerprint']:
                raise Conflict('This conference was updated by another manager. Refresh before saving.')
            # The editor displays minutes; unchanged fields retain native seconds and microseconds.
            if basic['start'] == current['basic']['start']:
                start = self.event.start_dt
            if basic['end'] == current['basic']['end']:
                end = self.event.end_dt
            entries = get_top_level_entries(self.event)
            if entries and ((start != self.event.start_dt and start > min(entry.start_dt for entry in entries)) or
                            end < max(entry.end_dt for entry in entries)):
                raise BadRequest('会议日期必须包含已排定的日程，请先在日程管理中调整。 / Conference dates must include all scheduled timetable entries.')
            values = {'title': title, 'start_dt': start, 'end_dt': end}
            if metadata['organizer_name'] != current['basic']['organizer_name']:
                values['organizer_info'] = str(escape(metadata['organizer_name']))
            if metadata['organizer_phone'] != current['basic']['organizer_phone']:
                values['contact_phones'] = [metadata['organizer_phone'], *(self.event.contact_phones or [])[1:]]
            region_changed = any(metadata[key] != current['basic'][key] for key in ('country', 'province', 'city'))
            if region_changed or metadata['detail_address'] != current['basic']['detail_address']:
                values['location_data'] = {'inheriting': False,
                                           'venue_name': location_name(metadata) if region_changed else self.event.venue_name,
                                           'room_name': self.event.room_name, 'address': metadata['detail_address']}
            # Preserve existing rich introduction markup when its plain text was not edited.
            if description != current['basic']['description']:
                values['description'] = f'<p>{escape(description)}</p>'.replace('\n', '<br>')
            with track_time_changes(), track_location_changes():
                update_event(self.event, **values)
            YujianSitePlugin.event_settings.set_multi(self.event, {
                'conference_metadata': metadata, 'basic_revision': current['revision'] + 1})
            return response(get_basic_payload(self.event))

    bp.add_url_rule('/api/conferences/metadata-options', 'metadata_options', RHMetadataOptions, methods=['GET'])
    bp.add_url_rule('/api/conferences/<int:event_id>/basic', 'basic', RHBasic, methods=['GET', 'PUT'])

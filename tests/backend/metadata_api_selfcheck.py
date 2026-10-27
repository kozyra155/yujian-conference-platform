"""Disposable metadata API fixtures; no real events or outbound mail are used."""
import json
import uuid
import warnings
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

from indico.web.flask.app import make_app
from indico.core.config import config
from indico.core.db import db
from indico.modules.auth import Identity
from indico.modules.events import Event
from indico.modules.events.operations import update_event
from indico.modules.events.timetable.models.breaks import Break
from indico.modules.events.timetable.models.entries import TimetableEntry
from indico.modules.users import User
from indico.modules.users.operations import create_user

app = make_app(config_override={'EMAIL_BACKEND': 'indico.vendor.django_mail.backends.locmem.EmailBackend',
                                'SMTP_USE_CELERY': False})
app.config.update(REPL=True, TESTING=True)
suffix = uuid.uuid4().hex[:12]
users, events = [], []
with app.app_context():
    base = config.BASE_URL


def login(client, user_id):
    with app.app_context(), client.session_transaction() as session:
        session.set_session_user(User.get(user_id))
    return {'X-CSRF-Token': json.loads(client.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']}


def check(result, status):
    assert result.status_code == status, (result.status_code, result.get_data(as_text=True)[:200])
    return result.json


def mutation(payload, basic=None):
    return {key: payload[key] for key in ('revision', 'fingerprint') if key in payload} | {
        'basic': payload['basic'] if basic is None else basic}


try:
    with app.test_request_context(base_url=base):
        for role in ('owner', 'other'):
            user = create_user(f'metadata-{role}-{suffix}@example.invalid',
                               {'first_name': 'Metadata fixture', 'last_name': role},
                               Identity(provider='indico', identifier=f'metadata-{role}-{suffix}', password=uuid.uuid4().hex))
            db.session.flush()
            users.append(user.id)
        db.session.commit()
    owner, other, anon = app.test_client(), app.test_client(), app.test_client()
    headers, other_headers = login(owner, users[0]), login(other, users[1])
    options = check(owner.get('/api/conferences/metadata-options'), 200)
    assert len(options['subject_domains']) == 45 and len(options['planned_indexing']) == 17
    assert any(country['value'] == '中国' for country in options['countries'])
    legacy = {'title': f'会议资料兼容验收 {suffix}', 'start': '2030-06-10T09:00', 'end': '2030-06-12T17:00',
              'location': '武汉', 'description': '兼容旧创建调用\n第二段会议简介', 'template': 'industry'}
    event = check(owner.post('/api/conferences/', json=legacy, headers=headers), 201)
    events.append(event['id'])
    assert check(owner.get(f"/api/conferences/{event['id']}/basic"), 200)['basic']['description'] == legacy['description']
    assert event['location'] == '武汉' and event['organizer_name'] == '' and event['phase'] == 'upcoming'
    metadata = {'organizer_name': '测试主办方', 'organizer_phone': '010-12345678', 'country': '中国',
                'province': '湖北省', 'city': '武汉市', 'detail_address': '待定',
                'subject_domains': ['数学', '人工智能'], 'planned_indexing': ['SCI', 'EI']}
    event = check(owner.post('/api/conferences/', json=legacy | metadata, headers=headers), 201)
    events.append(event['id'])
    assert event['subject_domains'] == metadata['subject_domains']
    assert event['planned_indexing'] == ['SCI', 'EI']
    url = f"/api/conferences/{event['id']}/basic"
    with app.test_request_context(base_url=base):
        current = Event.get(event['id'])
        current.description = '<p>保留 <strong>富文本</strong> 与图片</p><img src="/portal-assets/logo.png">'
        current.contact_phones = ['010-12345678', '027-87654321']
        original_description = str(current.description)
        db.session.commit()
    payload = check(owner.get(url), 200)
    assert payload['basic']['detail_address'] == '待定'
    check(anon.get(url), 401)
    check(other.get(url), 403)
    update = mutation(payload)
    check(owner.put(url, json=update), 400)
    check(other.put(url, json=update, headers=other_headers), 403)
    check(owner.put(url, json=update | {'basic': payload['basic'] | {'subject_domains': ['unknown']}}, headers=headers), 400)
    saved = check(owner.put(url, json=update, headers=headers), 200)
    assert saved['revision'] == 1
    with app.test_request_context(base_url=base):
        current = Event.get(event['id'])
        assert str(current.description) == original_description
        assert current.contact_phones == ['010-12345678', '027-87654321'], 'Preserve secondary native phone numbers'
        assert current.address == '待定' and '武汉市' in current.venue_name
        assert current.organizer_info == '测试主办方'
    check(owner.put(url, json=update, headers=headers), 409)
    with app.test_request_context(base_url=base):
        Event.get(event['id']).is_locked = True
        db.session.commit()
    check(owner.get(url), 200)
    check(owner.put(url, json=mutation(saved), headers=headers), 403)
    with app.test_request_context(base_url=base):
        Event.get(event['id']).is_locked = False
        db.session.commit()
    changed = saved['basic'] | {'description': '修改后的简介\n第二段 <script>仅文本</script>', 'organizer_phone': '020-11223344'}
    clients = [app.test_client(), app.test_client()]
    tokens = [login(client, users[0]) for client in clients]
    def save(pair):
        client, csrf = pair
        return client.put(url, json=mutation(saved, changed), headers=csrf).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(save, zip(clients, tokens)))
    assert sorted(statuses) == [200, 409], statuses
    with app.test_request_context(base_url=base):
        current = Event.get(event['id'])
        assert '<script>' not in str(current.description)
        assert current.contact_phones == ['020-11223344', '027-87654321']
        db.session.add(TimetableEntry(event=current, start_dt=current.start_dt + timedelta(days=1),
                                     object=Break(title='Metadata fixture break', duration=timedelta(minutes=30))))
        db.session.commit()
    latest = check(owner.get(url), 200)
    assert latest['basic']['description'] == changed['description'], 'Introduction must retain typed line breaks'
    for dates in ({'end': '2030-06-10T17:00'}, {'start': '2030-06-12T09:00'}):
        check(owner.put(url, json=mutation(latest, latest['basic'] | dates), headers=headers), 400)
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        check(owner.put(url, json=mutation(latest, latest['basic'] | {'start': '2030-06-09T09:00'}), headers=headers), 200)
    before_native_edit = check(owner.get(url), 200)
    native_title = before_native_edit['basic']['title'] + ' 原生编辑'
    native_description = '<p>原生编辑器保存的<strong>新简介</strong></p>'
    with app.test_request_context(base_url=base):
        update_event(Event.get(event['id']), title=native_title, description=native_description)
        db.session.commit()
    check(owner.put(url, json=mutation(before_native_edit), headers=headers), 409)
    with app.test_request_context(base_url=base):
        current = Event.get(event['id'])
        assert current.title == native_title and str(current.description) == native_description
    print('metadata API selfcheck passed: legacy create, metadata create, ACL, CSRF, lock, validation, rich text, native fields, concurrent revision')
finally:
    with app.test_request_context(base_url=base):
        db.session.rollback()
        for event_id in events:
            event = Event.get(event_id)
            if event:
                event.is_locked = False
                event.is_deleted = True
        for user_id in users:
            user = User.get(user_id)
            if user:
                user.is_deleted = True
        db.session.commit()

"""Exercise native matchmaking registration on disposable events, with memory-only email."""
import importlib.util
import json
import os
import uuid
from datetime import timedelta

os.environ['PYTEST_CURRENT_TEST'] = 'verify_interests'

from indico.web.flask.app import make_app
from indico.core.db import db
from indico.modules.auth import Identity
from indico.modules.users import User
from indico.modules.users.operations import create_user
from indico.modules.events import Event
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.invitations import RegistrationInvitation
from indico.modules.events.registration.models.registrations import Registration
from indico.modules.events.registration.util import create_personal_data_fields
from indico.util.date_time import now_utc
from indico.vendor import django_mail as mail
from indico.web.flask.util import url_for
from yujian_site import YujianSitePlugin

assert importlib.util.find_spec('yujian_site.interests'), 'Missing native intent registration implementation'
from yujian_site.interests import INTEREST_TYPES, sync_interest_forms

app = make_app(config_override={'EMAIL_BACKEND': 'indico.vendor.django_mail.backends.locmem.EmailBackend',
                                'SMTP_USE_CELERY': False})
app.config.update(TESTING=True, REPL=True)
suffix = uuid.uuid4().hex[:10]
user_ids = []
event_id = None


def login(client, user_id):
    with app.app_context(), client.session_transaction() as session:
        session.set_session_user(User.get(user_id))
    return json.loads(client.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']


try:
    with app.test_request_context():
        for role in ('owner', 'attendee', 'outsider'):
            name = f'intent-check-{role}-{suffix}'
            user = create_user(name + '@conference.test', {'first_name': '意向验收', 'last_name': role},
                               Identity(provider='indico', identifier=name, password=uuid.uuid4().hex))
            db.session.flush()
            user_ids.append(user.id)
        db.session.commit()
    owner = app.test_client()
    token = login(owner, user_ids[0])
    created = owner.post('/api/conferences/', json={
        'title': f'意向登记验收 {suffix}', 'start': '2027-11-20T09:00', 'end': '2027-11-22T17:00',
        'location': '武汉', 'description': '隔离验收，不发送邮件。', 'template': 'academic-full'},
        headers={'X-CSRF-Token': token})
    assert created.status_code == 201, created.status_code
    event_id = created.json['id']
    payload = owner.get(f'/api/conferences/{event_id}/content').json
    payload['content']['matchmaking']['enabled'] = True
    for section in payload['content']['sections']:
        if section['key'] == 'matchmaking':
            section['enabled'] = True
    save_data = {'revision': payload['revision'], 'template': payload['template'], 'content': payload['content']}
    assert owner.put(f'/api/conferences/{event_id}/content', json=save_data).status_code == 400
    saved = owner.put(f'/api/conferences/{event_id}/content', json=save_data,
                      headers={'X-CSRF-Token': token})
    assert saved.status_code == 200, ('CSRF protected intent enable', saved.status_code)
    with app.test_request_context():
        event = Event.get(event_id)
        ordinary = RegistrationForm(event=event, title='普通报名', currency='CNY',
                                    start_dt=now_utc() - timedelta(days=1), end_dt=None,
                                    notification_sender_address='no-reply@example.invalid')
        create_personal_data_fields(ordinary)
        db.session.add(ordinary)
        db.session.flush()
        ordinary_id = ordinary.id
        ordinary_start = ordinary.start_dt
        from yujian_site.site_content import get_content_payload
        content = get_content_payload(event)['content']
        content['matchmaking'] = {'enabled': True, 'text': '登记对接需求', 'text_en': '', 'activities': []}
        sync_interest_forms(event, content)
        YujianSitePlugin.event_settings.set(event, 'content', content)
        db.session.flush()
        mapping = YujianSitePlugin.event_settings.get(event, 'interest_forms')
        ids = {kind: info['id'] for kind, info in mapping.items()}
        assert set(ids) == set(INTEREST_TYPES) and len(set(ids.values())) == 3
        sync_interest_forms(event, content)
        assert RegistrationForm.query.filter_by(event_id=event_id).count() == 4, 'idempotent provisioning'
        urls = {}
        for kind, form_id in ids.items():
            form = RegistrationForm.get(form_id)
            assert form.private and form.require_login and form.is_open
            assert form.base_price == 0 and not form.tickets_enabled
            assert not form.organizer_notifications_enabled and not form.notification_sender_address
            assert form.participant_list_disabled and not form.publish_registration_count
            assert all(not f.versioned_data.get('price') for f in form.active_fields)
            titles = {f.title for f in form.active_fields}
            assert {'单位 / Organization', '联系方式 / Phone', '是否计划参会 / Attendance plan'} <= titles
            urls[kind] = url_for('event_registration.display_regform', form.locator.token)
        assert ordinary.start_dt == ordinary_start and ordinary.end_dt is None
        db.session.commit()
    public = app.test_client()
    assert public.get(f'/event/{event_id}/interest/').status_code in (302, 403), 'draft protection'
    assert owner.post(f'/api/conferences/{event_id}/publication', json={'published': True},
                      headers={'X-CSRF-Token': token}).status_code == 200
    assert f'/event/{event_id}/interest/' in public.get(f'/event/{event_id}/').get_data(as_text=True)
    with app.app_context():
        before = RegistrationForm.query.filter_by(event_id=event_id).count()
    landing = public.get(f'/event/{event_id}/interest/')
    assert landing.status_code == 200, landing.status_code
    html = landing.get_data(as_text=True)
    for kind in INTEREST_TYPES:
        assert INTEREST_TYPES[kind]['title'] in html
    with app.app_context():
        assert RegistrationForm.query.filter_by(event_id=event_id).count() == before, 'GET must not provision'
    attendee = app.test_client()
    attendee_token = login(attendee, user_ids[1])
    outsider = app.test_client()
    login(outsider, user_ids[2])
    mails_before = len(getattr(mail, 'outbox', []))
    submitted_data = {}
    for kind, form_url in urls.items():
        assert public.post(form_url, json={}).status_code in (400, 403), 'anonymous POST forbidden'
        assert attendee.get(form_url).status_code == 200
        with app.app_context():
            form = RegistrationForm.get(ids[kind])
            data = {'first_name': '意向验收', 'last_name': 'attendee',
                    'email': f'intent-check-attendee-{suffix}@conference.test',
                    'affiliation': '隔离测试机构', 'phone': '13800000000'}
            for field in form.active_fields:
                if field.html_field_name in data:
                    continue
                if field.input_type in ('single_choice', 'multi_choice'):
                    data[field.html_field_name] = {field.versioned_data['choices'][0]['id']: 1}
                elif field.is_required:
                    data[field.html_field_name] = '原生意向数据验收'
        submitted_data[kind] = data
        invalid = dict(data)
        invalid.pop('phone')
        bad = attendee.post(form_url, json=invalid, headers={'X-CSRF-Token': attendee_token})
        assert bad.status_code == 422, ('required contact', bad.status_code)
        submitted = attendee.post(form_url, json=data, headers={'X-CSRF-Token': attendee_token})
        assert submitted.status_code == 200 and 'redirect' in (submitted.json or {}), (
            'native intent submission', kind, submitted.status_code, submitted.get_data(as_text=True)[:500])
        with app.app_context():
            record = Registration.query.filter_by(registration_form_id=ids[kind], user_id=user_ids[1]).one()
            assert record.state.name == 'complete' and not record.price
            from yujian_site.payments import get_order
            assert get_order(record) is None, 'intent submissions must never create payment orders'
            assert any(row.data == '原生意向数据验收' for row in record.data)
        path = f'/event/{event_id}/manage/registration/{ids[kind]}/registrations/'
        assert owner.get(path).status_code == 200
        with app.app_context():
            all_fields = [field.id for field in RegistrationForm.get(ids[kind]).active_fields]
        customized = owner.post(path + 'customize', data={'visible_items': json.dumps(all_fields),
                                                          'csrf_token': token},
                                 headers={'X-CSRF-Token': token})
        assert customized.status_code == 200, 'organizer can select all intent data columns'
        export = owner.get(path + 'registrations.csv')
        assert export.status_code == 200 and '意向验收' in export.get_data(as_text=True)
        assert '原生意向数据验收' in export.get_data(as_text=True), 'CSV includes complete intent data'
        assert outsider.get(path).status_code == 403, 'registrations remain private'
    assert len(getattr(mail, 'outbox', [])) == mails_before, 'intent submissions must send zero emails'
    ordinary_submission = attendee.post(f'/event/{event_id}/registrations/{ordinary_id}/', json={
        'first_name': '意向验收', 'last_name': 'attendee',
        'email': f'intent-check-attendee-{suffix}@conference.test', 'affiliation': '隔离测试机构'},
        headers={'X-CSRF-Token': attendee_token})
    assert ordinary_submission.status_code == 200 and 'redirect' in (ordinary_submission.json or {})
    assert len(getattr(mail, 'outbox', [])) == mails_before + 1, 'ordinary registration emails are unaffected'
    with app.test_request_context():
        event = Event.get(event_id)
        closed_by_admin = RegistrationForm.get(ids['technology'])
        closed_by_admin.start_dt = None
        sync_interest_forms(event, content)
        assert closed_by_admin.start_dt is None, 'content saves preserve manual closure'
        content['matchmaking']['enabled'] = False
        sync_interest_forms(event, content)
        assert all(not RegistrationForm.get(form_id).is_open for form_id in ids.values())
        YujianSitePlugin.event_settings.set(event, 'content', content)
        db.session.commit()
    assert public.get(f'/event/{event_id}/interest/').status_code == 404
    for kind, form_url in urls.items():
        data = dict(submitted_data[kind], email=f'intent-check-outsider-{suffix}@conference.test')
        response = outsider.post(form_url, json=data, headers={'X-CSRF-Token': login(outsider, user_ids[2])})
        assert 'redirect' not in (response.json or {}), 'disabled native direct forms cannot accept submissions'
        with app.app_context():
            assert Registration.query.filter_by(registration_form_id=ids[kind], user_id=user_ids[2]).count() == 0
    with app.test_request_context():
        invitation = RegistrationInvitation(registration_form=RegistrationForm.get(ids['enterprise']),
                                             email=f'intent-check-outsider-{suffix}@conference.test',
                                             first_name='意向验收', last_name='outsider', affiliation='隔离测试机构')
        db.session.add(invitation)
        db.session.flush()
        invitation_url = url_for('event_registration.display_regform', invitation.locator.uuid)
        db.session.commit()
    invited_data = dict(submitted_data['enterprise'], email=f'intent-check-outsider-{suffix}@conference.test')
    invited = outsider.post(invitation_url, json=invited_data,
                             headers={'X-CSRF-Token': login(outsider, user_ids[2])})
    assert 'redirect' not in (invited.json or {}), 'disabled intent also rejects existing invitation links'
    with app.test_request_context():
        event = Event.get(event_id)
        content['matchmaking']['enabled'] = True
        sync_interest_forms(event, content)
        assert RegistrationForm.get(ids['technology']).start_dt is None
        assert RegistrationForm.get(ids['enterprise']).is_open
        assert RegistrationForm.get(ids['investment']).is_open
        assert RegistrationForm.get(ordinary_id).start_dt == ordinary_start
        db.session.commit()
    result = {'passed': True, 'forms': 3, 'native_submissions': 3, 'organizer_csv_export': True,
              'private_acl': True, 'disable_closes_native_forms': True, 'emails_sent': 0}
finally:
    with app.test_request_context():
        db.session.rollback()
        if event_id:
            event = Event.get(event_id)
            assert event.title.startswith('意向登记验收 ')
            event.is_deleted = True
        for user_id in user_ids:
            user = User.get(user_id)
            assert user.email.startswith('intent-check-') and user.email.endswith('@conference.test')
            user.is_deleted = True
        db.session.commit()

print(json.dumps(result))

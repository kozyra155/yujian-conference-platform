"""Verify that complete-site actions reach real native submissions, without external mail."""
import json
import os
import uuid
from datetime import timedelta

# Use the native validator's documented test-domain mode without external DNS or mail.
os.environ['PYTEST_CURRENT_TEST'] = 'verify_complete_business'

from indico.web.flask.app import make_app
from indico.core.db import db
from indico.modules.auth import Identity
from indico.modules.users import User
from indico.modules.users.operations import create_user
from indico.modules.events import Event
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration
from indico.modules.events.registration.util import create_personal_data_fields
from indico.modules.events.abstracts.models.abstracts import Abstract
from indico.util.date_time import now_utc

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
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        for role in ('owner', 'attendee'):
            name = f'complete-business-{role}-{suffix}'
            user = create_user(name + '@conference.test', {'first_name': '流程验收', 'last_name': role},
                               Identity(provider='indico', identifier=name, password=uuid.uuid4().hex))
            db.session.flush()
            user_ids.append(user.id)
        db.session.commit()
    owner = app.test_client()
    owner_token = login(owner, user_ids[0])
    created = owner.post('/api/conferences/', json={
        'title': f'完整建站业务验收 {suffix}', 'start': '2027-10-20T09:00', 'end': '2027-10-22T17:00',
        'location': '武汉', 'description': '临时会议，仅测试真实报名和投稿，不发送外部邮件。',
        'template': 'academic-full'}, headers={'X-CSRF-Token': owner_token})
    assert created.status_code == 201, ('complete template creation', created.status_code)
    event_id = created.json['id']
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        event = Event.get(event_id)
        assert event.has_feature('registration') and event.has_feature('abstracts')
        regform = RegistrationForm(event=event, title='临时报名表', currency='CNY',
                                   start_dt=now_utc() - timedelta(days=1), end_dt=now_utc() + timedelta(days=2),
                                   require_login=True, require_captcha=False,
                                   notification_sender_address='no-reply@example.invalid')
        create_personal_data_fields(regform)
        db.session.add(regform)
        event.cfa.open()
        db.session.flush()
        form_id = regform.id
        db.session.commit()
    payload = owner.get(f'/api/conferences/{event_id}/content').json
    payload['content']['actions']['registration']['enabled'] = True
    payload['content']['actions']['submission']['enabled'] = True
    saved = owner.put(f'/api/conferences/{event_id}/content', json={
        'revision': payload['revision'], 'template': 'academic-full', 'content': payload['content']},
        headers={'X-CSRF-Token': owner_token})
    assert saved.status_code == 200, ('save real action links', saved.status_code)
    assert owner.post(f'/api/conferences/{event_id}/publication', json={'published': True},
                      headers={'X-CSRF-Token': owner_token}).status_code == 200
    public = app.test_client()
    homepage = public.get(f'/event/{event_id}/').get_data(as_text=True)
    assert f'/event/{event_id}/registrations/' in homepage
    assert f'/event/{event_id}/abstracts/' in homepage
    attendee = app.test_client()
    attendee_token = login(attendee, user_ids[1])
    assert attendee.get(f'/event/{event_id}/registrations/{form_id}/').status_code == 200
    submitted = attendee.post(f'/event/{event_id}/registrations/{form_id}/', json={
        'first_name': '流程验收', 'last_name': 'attendee',
        'email': f'complete-business-attendee-{suffix}@conference.test', 'affiliation': '遇见科技'},
        headers={'X-CSRF-Token': attendee_token})
    assert submitted.status_code == 200 and 'redirect' in (submitted.json or {}), (
        'native registration submission', submitted.status_code, submitted.get_data(as_text=True)[:900])
    with app.app_context():
        registration = Registration.query.filter_by(registration_form_id=form_id, user_id=user_ids[1]).one()
        assert registration.first_name == '流程验收'
    author = {'first_name': '流程验收', 'last_name': 'attendee', 'email': f'complete-business-attendee-{suffix}@conference.test',
              'affiliation': '遇见科技', 'roles': ['primary', 'speaker']}
    abstract = attendee.post(f'/event/{event_id}/abstracts/submit', data={
        'title': '原生投稿端到端验收', 'description': '验证会议网站入口与原生摘要投稿记录相连。',
        'person_links': json.dumps([author]), 'csrf_token': attendee_token},
        headers={'X-CSRF-Token': attendee_token, 'X-Requested-With': 'XMLHttpRequest'})
    assert abstract.status_code == 200 and 'redirect' in (abstract.json or {}), (
        'native abstract submission', abstract.status_code, abstract.get_data(as_text=True)[:1100])
    with app.app_context():
        assert Abstract.query.filter_by(event_id=event_id, submitter_id=user_ids[1], title='原生投稿端到端验收').count() == 1
    assert owner.get(f'/event/{event_id}/manage/registration/{form_id}/registrations/').status_code == 200
    assert owner.get(f'/event/{event_id}/manage/abstracts/').status_code == 200
    assert owner.post(f'/api/conferences/{event_id}/publication', json={'published': False},
                      headers={'X-CSRF-Token': owner_token}).status_code == 200
    denied = attendee.get(f'/event/{event_id}/registrations/{form_id}/')
    assert denied.status_code == 403, ('withdrawal also blocks native registration pages', denied.status_code)
    result = {'passed': True, 'native_registration_submitted': True, 'native_abstract_submitted': True,
              'organizer_can_view_records': True, 'withdrawal_blocks_attendee': True, 'mail_backend': 'memory'}
finally:
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        db.session.rollback()
        if event_id:
            event = Event.get(event_id)
            assert event.title.startswith('完整建站业务验收 ')
            event.is_deleted = True
        for user_id in user_ids:
            user = User.get(user_id)
            assert user.email.startswith('complete-business-') and user.email.endswith('@conference.test')
            user.is_deleted = True
        db.session.commit()

print(json.dumps(result))

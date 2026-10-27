"""Real email verification, new-browser signup, conference return and native submissions; locmem only."""
import json
import html
import os
import re
import time
import uuid
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

os.environ['PYTEST_CURRENT_TEST'] = 'verify_conference_accounts'

from indico.web.flask.app import make_app
from indico.core.config import config
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
from indico.util.string import html_to_plaintext
from indico.util.signing import secure_serializer
from indico.vendor import django_mail

app = make_app(config_override={'EMAIL_BACKEND': 'indico.vendor.django_mail.backends.locmem.EmailBackend',
                                'SMTP_USE_CELERY': False})
app.config.update(TESTING=True, REPL=True)
with app.app_context():
    base = config.BASE_URL
suffix = uuid.uuid4().hex[:12]
username = f'conference-account-attendee-{suffix}'
email = username + '@example.com'
password = uuid.uuid4().hex + '!Q8'
user_ids, event_id = [], None


def csrf(client):
    return json.loads(client.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']


try:
    from yujian_site.conference_accounts import safe_conference_target
    with app.test_request_context(base_url=base):
        assert safe_conference_target('/event/999999999999999999999999/registrations/') is None, 'Out-of-range IDs must be rejected before database lookup'
    assert app.test_client().get('/event/999999999999999999999999/register/').status_code == 404
    with app.test_request_context(base_url=base):
        owner_user = create_user(f'conference-account-owner-{suffix}@conference.test',
                                 {'first_name': '账号验收', 'last_name': 'owner'},
                                 Identity(provider='indico', identifier=f'conference-account-owner-{suffix}',
                                          password=uuid.uuid4().hex))
        db.session.commit()
        user_ids.append(owner_user.id)
    owner = app.test_client()
    with app.app_context(), owner.session_transaction() as session:
        session.set_session_user(User.get(user_ids[0]))
    owner_token = csrf(owner)
    created = owner.post('/api/conferences/', json={
        'title': f'会议账号验收 {suffix}', 'start': '2027-10-20T09:00', 'end': '2027-10-22T17:00',
        'location': '武汉', 'description': '临时账号、邮箱验证和报名投稿验收。', 'template': 'academic-full'},
        headers={'X-CSRF-Token': owner_token})
    assert created.status_code == 201
    event_id = created.json['id']
    with app.test_request_context(base_url=base):
        event = Event.get(event_id)
        form = RegistrationForm(event=event, title='邮箱注册参会验收', currency='CNY',
                                start_dt=now_utc()-timedelta(days=1), end_dt=now_utc()+timedelta(days=2),
                                require_login=True, require_captcha=False,
                                notification_sender_address='no-reply@example.invalid')
        create_personal_data_fields(form)
        db.session.add(form)
        event.cfa.open()
        db.session.flush()
        form_id = form.id
        db.session.commit()
    assert owner.post(f'/api/conferences/{event_id}/publication', json={'published': True},
                      headers={'X-CSRF-Token': owner_token}).status_code == 200
    payload = owner.get(f'/api/conferences/{event_id}/content').json
    for action in ('registration', 'submission'):
        payload['content']['actions'][action]['enabled'] = True
    content_saved = owner.put(f'/api/conferences/{event_id}/content', json={
        'revision': payload['revision'], 'content': payload['content'], 'template': 'academic-full'},
        headers={'X-CSRF-Token': owner_token})
    assert content_saved.status_code == 200, ('temporary conference content', content_saved.status_code, content_saved.json)
    target = f'/event/{event_id}/registrations/{form_id}/'
    visitor = app.test_client()
    visitor.environ_base['REMOTE_ADDR'] = f'192.0.2.{int(suffix[:2],16) % 200 + 20}'
    homepage = visitor.get(f'/event/{event_id}/').get_data(as_text=True)
    assert 'data-guest-signup' in homepage and 'data-login-url' in homepage
    assert f'/login/?next=/event/{event_id}/registrations/' in homepage
    entry = visitor.get(f'/event/{event_id}/register/', query_string={'next': target})
    assert entry.status_code == 302, ('conference signup entry missing', entry.status_code)
    assert urlsplit(entry.location).path == '/register/'
    register_url = entry.location
    page = visitor.get(register_url)
    assert page.status_code == 200 and b'data-conference-auth' in page.data
    assert f'会议账号验收 {suffix}' in page.get_data(as_text=True)
    assert b'setupCaptchaWidget(' in page.data and b'name="csrf_token"' in page.data
    assert visitor.get('/login/', query_string={'next': target}).data.count(b'data-conference-auth') == 1
    assert b'data-conference-auth' not in visitor.get('/login/').data

    unverified = visitor.post(register_url, json={'email': email, 'username': username, 'password': password,
                                                'first_name': '参会者', 'last_name': '验收'},
                              headers={'X-CSRF-Token': csrf(visitor)})
    assert not (unverified.is_json and 'redirect' in unverified.json), 'Unverified email must not create an account'
    assert visitor.post(register_url, data={'email': email}).status_code == 400
    assert visitor.get('/register/?token=invalid').status_code == 400
    token = csrf(visitor)
    bad_captcha = visitor.post(register_url, data={'email': email, 'captcha': 'invalid',
                                                  'is_email_verification': '', 'csrf_token': token})
    assert bad_captcha.status_code == 200 and not getattr(django_mail, 'outbox', [])
    assert visitor.get('/api/captcha/generate').status_code == 200
    with app.app_context(), visitor.session_transaction() as session:
        answer = session['captcha_state']
    sent = visitor.post(register_url, data={'email': email, 'captcha': answer,
                                          'is_email_verification': '', 'csrf_token': token})
    assert sent.status_code == 302, ('native verification email request', sent.status_code, [html.unescape(error) for error in re.findall(r'data-error="([^"]+)"', sent.get_data(as_text=True))])
    assert b'data-email-sent="true"' in visitor.get(sent.location).data
    waiting = visitor.get(register_url)
    assert b'data-email-sent="true"' in waiting.data, 'Conference waiting status must survive refresh'
    assert b'data-verification-link-form' in waiting.data
    messages = [message for message in django_mail.outbox if email in message.to]
    assert len(messages) == 1
    verification_url = next(url for url in re.findall(r'https?://[^\s<>()]+', messages[0].body)
                            if urlsplit(url).path == '/register/')
    assert parse_qs(urlsplit(verification_url).query).get('next') == [target], 'Email must carry the conference target'

    # A fresh browser has no registration session from the email-request browser.
    fresh = app.test_client()
    verified = fresh.get(verification_url)
    assert verified.status_code == 302
    assert parse_qs(urlsplit(verified.location).query).get('next') == [target]
    assert parse_qs(urlsplit(verified.location).query).get('verified') == ['1']
    cookie_lost = app.test_client(use_cookies=False).get(verified.location)
    assert b'data-registration-cookie-lost' in cookie_lost.data
    assert b'data-conference-auth' in cookie_lost.data
    profile = fresh.get(verified.location)
    assert profile.status_code == 200 and b'id="signup-container"' in profile.data
    assert b'data-conference-auth' in profile.data
    with app.app_context(), fresh.session_transaction() as session:
        assert session['register_verified_email'] == email
        assert session['register_next_url'] == target
    changed_email = fresh.post('/register/', json={'email': 'different@example.com', 'username': username,
                                                  'password': password, 'first_name': '参会者', 'last_name': '验收'},
                               headers={'X-CSRF-Token': csrf(fresh)})
    assert changed_email.status_code in (400, 422), 'Email must match the verified address'
    registered = fresh.post('/register/', json={'email': email, 'username': username, 'password': password,
                                               'first_name': '参会者', 'last_name': '验收', 'affiliation': '遇见科技'},
                            headers={'X-CSRF-Token': csrf(fresh)})
    assert registered.status_code == 200 and registered.json['redirect'] == target
    with app.app_context():
        account = Identity.query.filter_by(provider='indico', identifier=username).one().user
        user_ids.append(account.id)
        assert account.email == email and not account.is_pending
    assert fresh.get(target).status_code == 200
    submitted = fresh.post(target, json={'first_name': '参会者', 'last_name': '验收', 'email': email,
                                         'affiliation': '遇见科技'}, headers={'X-CSRF-Token': csrf(fresh)})
    assert submitted.status_code == 200 and 'redirect' in submitted.json
    with app.app_context():
        assert Registration.query.filter_by(registration_form_id=form_id, user_id=user_ids[1]).count() == 1

    login_client = app.test_client()
    submission_target = f'/event/{event_id}/abstracts/'
    login_url = f'/login/?next={submission_target}'
    assert login_client.get(login_url).status_code == 200
    logged_in = login_client.post(login_url, data={'_provider': 'indico', 'identifier': email, 'password': password,
                                                  'csrf_token': csrf(login_client)})
    assert logged_in.status_code == 302 and urlsplit(logged_in.location).path == submission_target
    author = {'first_name': '参会者', 'last_name': '验收', 'email': email,
              'affiliation': '遇见科技', 'roles': ['primary', 'speaker']}
    submitted = login_client.post(f'/event/{event_id}/abstracts/submit', data={
        'title': '邮箱注册账号实际投稿', 'description': '邮箱验证创建账号后能实际投稿。',
        'person_links': json.dumps([author]), 'csrf_token': csrf(login_client)},
        headers={'X-CSRF-Token': csrf(login_client), 'X-Requested-With': 'XMLHttpRequest'})
    assert submitted.status_code == 200 and 'redirect' in submitted.json
    with app.app_context():
        assert Abstract.query.filter_by(event_id=event_id, submitter_id=user_ids[1]).count() == 1
    for invalid in ('https://evil.example/', '//evil.example/', f'/event/22/registrations/',
                    f'/event/{event_id}/../22/registrations/', f'/event/{event_id}/%2e%2e/22/',
                    f'/event/{event_id}/registrations/\\evil', f'/event/{event_id}/registrations/\r\n'):
        assert visitor.get(f'/event/{event_id}/register/', query_string={'next': invalid}).status_code == 400
    with app.test_request_context(base_url=base), patch('itsdangerous.timed.time.time', return_value=time.time()-7200):
        expired = secure_serializer.dumps(email, salt='register-email')
    assert visitor.get('/register/', query_string={'token': expired}).status_code == 400
    assert owner.post(f'/api/conferences/{event_id}/publication', json={'published': False},
                      headers={'X-CSRF-Token': owner_token}).status_code == 200
    denied = visitor.get(f'/event/{event_id}/register/')
    assert denied.status_code in (302,403,404), ('private conference signup must be denied', denied.status_code)
    if denied.status_code == 302:
        assert urlsplit(denied.location).path == '/login/'
        denied = visitor.get(denied.location)
    assert f'会议账号验收 {suffix}' not in denied.get_data(as_text=True)
    assert b'data-conference-auth' not in visitor.get('/login/', query_string={'next': target}).data
    result = {'passed': True, 'email_verification_required': True, 'native_captcha_csrf': True,
              'new_browser_email_return': True, 'native_account_created': True, 'email_login': True,
              'real_registration': True, 'real_submission': True, 'safe_redirects': True,
              'private_conference_context_hidden': True, 'mail_backend': 'memory'}
finally:
    with app.test_request_context(base_url=base):
        db.session.rollback()
        if event_id:
            event = Event.get(event_id)
            assert event.id not in (22,61,171) and event.title.startswith('会议账号验收 ')
            event.is_deleted = True
        for user in User.query.filter(User.email.like(f'conference-account-%-{suffix}@%')):
            user.is_deleted = True
        db.session.commit()
print(json.dumps(result))

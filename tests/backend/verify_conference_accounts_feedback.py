"""Registration recovery regression checks; isolated locmem mail, no accounts created."""
import json
import os
import re
import time
import uuid
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from pathlib import Path

os.environ['PYTEST_CURRENT_TEST'] = 'verify_conference_accounts_feedback'

from indico.web.flask.app import make_app
from indico.util.signing import secure_serializer
from indico.vendor import django_mail

app = make_app(config_override={'EMAIL_BACKEND': 'indico.vendor.django_mail.backends.locmem.EmailBackend',
                                'SMTP_USE_CELERY': False})
app.config.update(TESTING=True, REPL=True)
email = f'feedback-signup-{uuid.uuid4().hex}@example.com'
client = app.test_client()
client.environ_base['REMOTE_ADDR'] = '192.0.2.211'

assert client.get('/register/').status_code == 200
csrf = json.loads(client.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']
assert client.get('/api/captcha/generate').status_code == 200
with app.app_context(), client.session_transaction() as session:
    answer = session['captcha_state']
response = client.post('/register/', data={'email': email, 'captcha': answer,
                                         'csrf_token': csrf, 'is_email_verification': ''})
assert response.status_code == 302
first = client.get(response.location)
assert b'data-email-sent="true"' in first.data
assert b'data-email-sent="true"' in client.get('/register/').data, 'Refreshing must keep waiting status'
assert email.encode() not in first.data, 'Pending email must not be displayed in full'
assert b'data-verification-link-form' in first.data, 'Original browser needs explicit email-link continuation'

message = next(message for message in django_mail.outbox if email in message.to)
link = next(url for url in re.findall(r'https?://[^\s<>()]+', message.body)
            if urlsplit(url).path == '/register/')
assert parse_qs(urlsplit(link).query).get('token')
fresh = app.test_client()
verified = fresh.get(link)
assert verified.status_code == 302
assert parse_qs(urlsplit(verified.location).query).get('verified') == ['1']
profile = fresh.get(verified.location)
assert b'id="signup-container"' in profile.data
assert b'data-email-sent="true"' not in profile.data
assert verified.headers['Cache-Control'] == 'private, no-store'

# Dropping the cookie between token verification and the redirect must be explicit.
lost = app.test_client(use_cookies=False).get(verified.location)
assert b'data-registration-cookie-lost' in lost.data
assert b'id="meet-register-email-form"' not in lost.data
assert b'id="signup-container"' not in lost.data
assert client.get('/register/?token=invalid').status_code == 400
with app.test_request_context(), patch('itsdangerous.timed.time.time', return_value=time.time() - 7200):
    expired = secure_serializer.dumps(email, salt='register-email')
assert client.get('/register/', query_string={'token': expired}).status_code == 400
assert client.get('/register/?verified=1').data.count(b'id="signup-container"') == 0
assert client.post('/register/', data={'email': email}).status_code == 400
with app.app_context(), client.session_transaction() as session:
    session['_meet_registration_pending'] = {'email': email, 'sent_at': time.time() - 7200}
assert b'id="meet-register-email-form"' in client.get('/register/').data, 'Expired waiting state must reset'
with app.app_context(), fresh.session_transaction() as session:
    assert '_meet_registration_pending' not in session, 'Verification must clear pending state'
assert client.get('/logout/').status_code == 302
assert b'id="meet-register-email-form"' in client.get('/register/').data
assert len(django_mail.outbox) == 1
Path('/tmp/registration-feedback-ui.json').write_text(json.dumps({
    'waiting': first.get_data(as_text=True), 'cookie_lost': lost.get_data(as_text=True),
    'profile': profile.get_data(as_text=True)}), encoding='utf-8')
print(json.dumps({'passed': True, 'global_pending_refresh': True, 'new_browser': True,
                  'cookie_loss_explicit': True, 'forged_marker_cannot_verify': True,
                  'pending_expiry_logout_clear': True,
                  'invalid_expired_rejected': True, 'mail_backend': 'memory'}))

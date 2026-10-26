"""Keep native signup verification intact while making browser recovery explicit."""
from time import time

from flask import g, make_response, request, session

from indico.modules.auth.controllers import _send_confirmation
from indico.web.flask.util import url_for


def prepare_registration(rh, target):
    pending = session.get('_meet_registration_pending')
    if pending and time() - pending['sent_at'] >= 3600:
        session.pop('_meet_registration_pending', None)
        pending = None
    if pending:
        local, domain = pending['email'].rsplit('@', 1)
        g.registration_pending_email = f'{local[:1]}***@{domain}'
        if request.method == 'GET' and 'token' not in request.args:
            session['register_verification_email_sent'] = True
    g.registration_cookie_lost = (request.args.get('verified') == '1' and
                                  'register_verified_email' not in session and not session.user)

    def send_confirmation(email):
        # Carry conference context in the signed-email link, including for a fresh browser.
        response = _send_confirmation(email, 'register-email', 'auth.register',
                                      'auth/emails/register_verify_email.txt',
                                      url_args={'next': target} if target else {})
        session['_meet_registration_pending'] = {'email': email, 'sent_at': time()}
        session['register_verification_email_sent'] = True
        return response

    native_process = rh._process

    def process():
        response = make_response(native_process())
        if 'register_verified_email' in session or session.user:
            session.pop('_meet_registration_pending', None)
            session.pop('register_verification_email_sent', None)
        if ('token' in request.args and not session.user and
                'register_verified_email' in session and response.status_code == 302):
            # This marker only detects lost cookies; native signed tokens alone verify email.
            response.location = url_for('auth.register', verified='1', next=target)
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['Referrer-Policy'] = 'same-origin'
        return response

    rh._send_confirmation = send_confirmation
    rh._process = process

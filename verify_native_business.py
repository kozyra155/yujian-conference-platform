"""Real native business pages retain their controls inside the shared frame; locmem mail only."""
import json
import os
import re
import uuid
from datetime import timedelta

os.environ['PYTEST_CURRENT_TEST'] = 'verify_native_business'

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
from indico.modules.events.tracks.models.tracks import Track
from indico.util.date_time import now_utc

app = make_app(config_override={'EMAIL_BACKEND': 'indico.vendor.django_mail.backends.locmem.EmailBackend',
                                'SMTP_USE_CELERY': False})
app.config.update(TESTING=True, REPL=True)
suffix = uuid.uuid4().hex[:10]
user_ids = []
event_id = None
preview = os.environ.get('NATIVE_BUSINESS_PREVIEW') == '1'
preview_ready = False


def login(client, user_id):
    with app.app_context(), client.session_transaction() as session:
        session.set_session_user(User.get(user_id))
    return json.loads(client.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']


def page(client, path, original):
    response = client.get(path)
    assert response.status_code == 200, (path, response.status_code)
    html = response.get_data(as_text=True)
    assert 'class="meet-native-business' in html, ('native business frame missing', path)
    assert html.count('class="meet-native-workspace ') == 1, ('one frame only', path)
    assert html.count('id="flashed-messages"') == 1, ('one native flash container only', path)
    assert '/portal-assets/native-business.css' in html and '/portal-assets/native-business.js' in html
    assert original in html, ('native content/initialization lost', path, original)
    assert f'/event/{event_id}/' in html and '/participation/' in html
    return html


try:
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        for role in ('owner', 'attendee', 'reviewer'):
            name = f'native-business-{role}-{suffix}'
            user = create_user(name + '@conference.test', {'first_name': '原生界面', 'last_name': role},
                               Identity(provider='indico', identifier=name, password=uuid.uuid4().hex))
            db.session.flush()
            user_ids.append(user.id)
        db.session.commit()
    owner = app.test_client()
    token = login(owner, user_ids[0])
    created = owner.post('/api/conferences/', json={
        'title': f'原生业务界面验收 {suffix}', 'start': '2027-10-20T09:00', 'end': '2027-10-22T17:00',
        'location': '武汉', 'description': '临时原生界面测试', 'template': 'academic-full'},
        headers={'X-CSRF-Token': token})
    assert created.status_code == 201, created.status_code
    event_id = created.json['id']
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        event = Event.get(event_id)
        regform = RegistrationForm(event=event, title='原生界面临时报名表', currency='CNY',
                                   start_dt=now_utc() - timedelta(days=1), end_dt=now_utc() + timedelta(days=2),
                                   require_login=True, require_captcha=False,
                                   notification_sender_address='no-reply@example.invalid')
        create_personal_data_fields(regform)
        db.session.add(regform)
        db.session.add(RegistrationForm(event=event, title='第二临时报名表', currency='CNY',
                                       start_dt=now_utc() - timedelta(days=1), end_dt=now_utc() + timedelta(days=2)))
        event.cfa.open()
        db.session.flush()
        form_id = regform.id
        db.session.commit()
    management = f'/event/{event_id}/manage/'
    page(owner, management + 'registration/', 'setupRegistrationFormListPage();')
    page(owner, management + 'registration/create', 'name="csrf_token"')
    page(owner, management + f'registration/{form_id}/', 'data-ajax-dialog')
    page(owner, management + f'registration/{form_id}/edit', 'name="csrf_token"')
    page(owner, management + f'registration/{form_id}/form/', 'id="registration-form-setup-container"')
    page(owner, management + f'registration/{form_id}/registrations/', 'reglist')
    page(owner, management + 'abstracts/', 'data-ajax-dialog')
    page(owner, management + 'abstracts/list/', 'abstract-list')
    assert owner.post(f'/api/conferences/{event_id}/publication', json={'published': True},
                      headers={'X-CSRF-Token': token}).status_code == 200
    attendee = app.test_client()
    attendee_token = login(attendee, user_ids[1])
    page(attendee, f'/event/{event_id}/registrations/', 'regforms-list')
    page(attendee, f'/event/{event_id}/registrations/{form_id}/', 'id="registration-form-submission-container"')
    page(attendee, f'/event/{event_id}/abstracts/', 'setupCallForAbstractsPage(')
    fragment = attendee.get(f'/event/{event_id}/abstracts/submit', headers={'X-Requested-With': 'XMLHttpRequest'})
    assert fragment.status_code == 200 and fragment.is_json
    assert 'meet-native-business' not in fragment.get_data(as_text=True), 'AJAX dialogs must stay fragments'
    assert 'csrf_token' in fragment.get_data(as_text=True)
    submitted = attendee.post(f'/event/{event_id}/registrations/{form_id}/', json={
        'first_name': '原生界面', 'last_name': 'attendee',
        'email': f'native-business-attendee-{suffix}@conference.test', 'affiliation': '遇见科技'},
        headers={'X-CSRF-Token': attendee_token})
    assert submitted.status_code == 200 and 'redirect' in (submitted.json or {})
    author = {'first_name': '原生界面', 'last_name': 'attendee',
              'email': f'native-business-attendee-{suffix}@conference.test',
              'affiliation': '遇见科技', 'roles': ['primary', 'speaker']}
    submitted = attendee.post(f'/event/{event_id}/abstracts/submit', data={
        'title': '原生业务界面稿件', 'description': '原生稿件详情与审稿界面测试。',
        'person_links': json.dumps([author]), 'csrf_token': attendee_token},
        headers={'X-CSRF-Token': attendee_token, 'X-Requested-With': 'XMLHttpRequest'})
    assert submitted.status_code == 200 and 'redirect' in (submitted.json or {})
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        registration_id = Registration.query.filter_by(registration_form_id=form_id, user_id=user_ids[1]).one().id
        abstract = Abstract.query.filter_by(event_id=event_id, submitter_id=user_ids[1]).one()
        abstract_id = abstract.id
        event = Event.get(event_id)
        track = Track(event=event, title='原生界面临时审稿专题', position=0)
        db.session.add(track)
        event.update_principal(User.get(user_ids[2]), add_permissions={'abstract_reviewer'})
        track.update_principal(User.get(user_ids[2]), add_permissions={'review'})
        abstract.reviewed_for_tracks.add(track)
        db.session.flush()
        track_id = track.id
        db.session.commit()
    page(owner, management + f'registration/{form_id}/registrations/{registration_id}/', 'registration-details')
    page(owner, management + f'abstracts/{abstract_id}/', 'setupAbstractJudgment(')
    page(attendee, f'/event/{event_id}/abstracts/{abstract_id}/', 'setupReviewingPage();')
    reviewer = app.test_client()
    login(reviewer, user_ids[2])
    page(reviewer, f'/event/{event_id}/abstracts/reviewing/', '原生界面临时审稿专题')
    page(reviewer, f'/event/{event_id}/abstracts/reviewing/{track_id}/', 'abstract-list')
    page(reviewer, f'/event/{event_id}/abstracts/{abstract_id}/', 'setupReviewingPage();')
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        Event.get(event_id).update_principal(User.get(user_ids[1]), add_permissions={'registration_moderation'})
        db.session.commit()
    limited_html = page(attendee, management + 'registration/', 'setupRegistrationFormListPage();')
    limited_tabs = re.search(r'<nav class="meet-business-tabs".*?</nav>', limited_html, re.S).group()
    assert 'manage/registration/' in limited_tabs and 'manage/abstracts/' not in limited_tabs, 'Scoped staff navigation must match native permissions'
    assert f'/conference/{event_id}/operations/' not in limited_html, 'Full-management back link must be hidden from scoped staff'
    # Other event management remains native even for a managed event.
    ordinary = owner.get(management).get_data(as_text=True)
    assert 'class="meet-native-business' not in ordinary
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        from yujian_site import YujianSitePlugin
        YujianSitePlugin.event_settings.set(Event.get(event_id), 'managed', False)
        db.session.commit()
    unmanaged = owner.get(management + 'registration/').get_data(as_text=True)
    assert 'class="meet-native-business' not in unmanaged
    result = {'passed': True, 'native_pages': 18, 'scoped_staff_navigation': True, 'native_csrf_and_init': True,
              'ajax_fragments_preserved': True, 'scope_exclusions': True, 'mail_backend': 'memory'}
    if preview:
        with app.test_request_context(base_url='http://192.168.2.36:12880'):
            YujianSitePlugin.event_settings.set(Event.get(event_id), 'managed', True)
            db.session.commit()
        result['preview'] = {'event_id': event_id, 'form_id': form_id, 'registration_id': registration_id,
                             'abstract_id': abstract_id, 'track_id': track_id, 'user_ids': user_ids,
                             'cookies': {role: [{'name': cookie.key, 'value': cookie.value,
                                                  'domain': 'localhost', 'path': cookie.path,
                                                  'httpOnly': cookie.http_only, 'sameSite': 'Lax'}
                                                 for cookie in client._cookies.values()]
                                         for role, client in [('owner', owner), ('attendee', attendee),
                                                              ('reviewer', reviewer)]}}
        preview_ready = True
finally:
    if not preview_ready:
        with app.test_request_context(base_url='http://192.168.2.36:12880'):
            db.session.rollback()
            if event_id:
                event = Event.get(event_id)
                assert event.title.startswith('原生业务界面验收 ')
                event.is_deleted = True
            for user_id in user_ids:
                user = User.get(user_id)
                assert user.email.startswith('native-business-') and user.email.endswith('@conference.test')
                user.is_deleted = True
            db.session.commit()

print(json.dumps(result))

"""Verify that complete-site actions reach real native submissions, without external mail."""
import json
import os
import uuid
from datetime import timedelta

# Use the native validator's documented test-domain mode without external DNS or mail.
os.environ['PYTEST_CURRENT_TEST'] = 'verify_business_workspace'

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
from indico.modules.events.abstracts.models.abstracts import AbstractState
from indico.modules.events.abstracts.models.persons import AbstractPersonLink
from indico.modules.events.models.persons import EventPerson
from indico.modules.events.tracks.models.tracks import Track
from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.registration.models.registrations import RegistrationState
from indico.modules.events.contributions.models.persons import AuthorType
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
        for role in ('owner', 'attendee', 'other', 'reviewer'):
            name = f'workspace-business-{role}-{suffix}'
            user = create_user(name + '@conference.test', {'first_name': '流程验收', 'last_name': role},
                               Identity(provider='indico', identifier=name, password=uuid.uuid4().hex))
            db.session.flush()
            user_ids.append(user.id)
        db.session.commit()
    owner = app.test_client()
    owner_token = login(owner, user_ids[0])
    created = owner.post('/api/conferences/', json={
        'title': f'业务工作台验收 {suffix}', 'start': '2027-10-20T09:00', 'end': '2027-10-22T17:00',
        'location': '武汉', 'description': '临时会议，仅测试真实报名和投稿，不发送外部邮件。',
        'template': 'academic-full'}, headers={'X-CSRF-Token': owner_token})
    assert created.status_code == 201, ('complete template creation', created.status_code)
    event_id = created.json['id']
    workspace = owner.get(f'/api/conferences/{event_id}/operations')
    assert workspace.status_code == 200, ('missing operations API', workspace.status_code)
    assert 'no-store' in workspace.headers['Cache-Control']
    assert owner.get('/api/participation/').status_code == 200
    anonymous = app.test_client()
    assert anonymous.get('/api/participation/').status_code == 401
    assert anonymous.get(f'/api/conferences/{event_id}/operations').status_code == 401
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        event = Event.get(event_id)
        assert event.has_feature('registration') and event.has_feature('abstracts')
        regform = RegistrationForm(event=event, title='临时报名表', currency='CNY',
                                   start_dt=now_utc() - timedelta(days=1), end_dt=now_utc() + timedelta(days=2),
                                   require_login=True, require_captcha=False, moderation_enabled=True,
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
    other = app.test_client()
    other_token = login(other, user_ids[2])
    reviewer = app.test_client()
    login(reviewer, user_ids[3])
    assert attendee.get(f'/api/conferences/{event_id}/operations').status_code == 403
    assert owner.get(f'/conference/{event_id}/operations/').status_code == 200
    assert attendee.get('/participation/').status_code == 200
    assert attendee.get(f'/event/{event_id}/registrations/{form_id}/').status_code == 200
    submitted = attendee.post(f'/event/{event_id}/registrations/{form_id}/', json={
        'first_name': '流程验收', 'last_name': 'attendee',
        'email': f'workspace-business-attendee-{suffix}@conference.test', 'affiliation': '遇见科技'},
        headers={'X-CSRF-Token': attendee_token})
    assert submitted.status_code == 200 and 'redirect' in (submitted.json or {}), (
        'native registration submission', submitted.status_code, submitted.get_data(as_text=True)[:900])
    with app.app_context():
        registration = Registration.query.filter_by(registration_form_id=form_id, user_id=user_ids[1]).one()
        assert registration.first_name == '流程验收'
        registration_id = registration.id
        registration_uuid = str(registration.uuid)
        ticket_uuid = str(registration.ticket_uuid)
    author = {'first_name': '流程验收', 'last_name': 'attendee', 'email': f'workspace-business-attendee-{suffix}@conference.test',
              'affiliation': '遇见科技', 'roles': ['primary', 'speaker']}
    abstract = attendee.post(f'/event/{event_id}/abstracts/submit', data={
        'title': '原生投稿端到端验收', 'description': '验证会议网站入口与原生摘要投稿记录相连。',
        'person_links': json.dumps([author]), 'csrf_token': attendee_token},
        headers={'X-CSRF-Token': attendee_token, 'X-Requested-With': 'XMLHttpRequest'})
    assert abstract.status_code == 200 and 'redirect' in (abstract.json or {}), (
        'native abstract submission', abstract.status_code, abstract.get_data(as_text=True)[:1100])
    with app.app_context():
        abstract_id = Abstract.query.filter_by(event_id=event_id, submitter_id=user_ids[1], title='原生投稿端到端验收').one().id
    # A second native participant must never appear in the first participant's private response.
    submitted_other = other.post(f'/event/{event_id}/registrations/{form_id}/', json={
        'first_name': '其他', 'last_name': 'other', 'email': f'workspace-business-other-{suffix}@conference.test',
        'affiliation': '其他单位'}, headers={'X-CSRF-Token': other_token})
    assert submitted_other.status_code == 200 and 'redirect' in submitted_other.json
    author_other = {'first_name': '其他', 'last_name': 'other', 'email': f'workspace-business-other-{suffix}@conference.test',
                    'affiliation': '其他单位', 'roles': ['primary', 'speaker']}
    submitted_other = other.post(f'/event/{event_id}/abstracts/submit', data={
        'title': '他人私有稿件', 'description': '不得泄漏到我的参会。', 'person_links': json.dumps([author_other]),
        'csrf_token': other_token}, headers={'X-CSRF-Token': other_token, 'X-Requested-With': 'XMLHttpRequest'})
    assert submitted_other.status_code == 200 and 'redirect' in submitted_other.json, (
        'second native abstract', submitted_other.status_code, submitted_other.get_data(as_text=True)[:1000])

    workspace = owner.get(f'/api/conferences/{event_id}/operations').json
    assert workspace['registration']['total'] == 2 and workspace['registration']['pending'] == 2
    assert workspace['registration']['forms'][0]['pending_count'] == 2
    assert workspace['submission']['total'] == 2 and workspace['submission']['pending'] == 2
    assert workspace['submission']['counts'] == {'submitted': 2}
    mine_response = attendee.get('/api/participation/')
    assert 'no-store' in mine_response.headers['Cache-Control']
    mine = mine_response.json
    assert [record['id'] for record in mine['registrations']] == [registration_id]
    assert mine['registrations'][0]['state'] == 'pending'
    assert [record['id'] for record in mine['submissions']] == [abstract_id]
    assert mine['reviews'] == [] and owner.get('/api/participation/').json['reviews'] == []
    assert registration_uuid not in mine_response.get_data(as_text=True)
    assert ticket_uuid not in mine_response.get_data(as_text=True)
    assert '他人私有稿件' not in mine_response.get_data(as_text=True)
    assert '@conference.test' not in mine_response.get_data(as_text=True)
    assert attendee.get(f'/api/participation/?user_id={user_ids[2]}').json == mine
    assert attendee.get(mine['registrations'][0]['url']).status_code == 200
    assert attendee.get(mine['submissions'][0]['url']).status_code == 200

    approved = owner.post(f'/event/{event_id}/manage/registration/{form_id}/registrations/{registration_id}/approve',
                          headers={'X-CSRF-Token': owner_token})
    assert approved.status_code == 200, ('native approval', approved.status_code)
    assert attendee.get('/api/participation/').json['registrations'][0]['state'] == 'complete'
    assert owner.get(f'/api/conferences/{event_id}/operations').json['registration']['pending'] == 1

    # Native links must serve full HTML documents rather than dialog JSON fragments.
    workspace = owner.get(f'/api/conferences/{event_id}/operations').json
    native_links = set(workspace['registration']['links'].values())
    native_links.update(workspace['submission']['links'].values())
    for key in ('url', 'settings_url', 'fields_url', 'list_url'):
        native_links.add(workspace['registration']['forms'][0][key])
    native_links.add(workspace['event']['feature_url'])
    for url in native_links:
        page = owner.get(url)
        assert page.status_code == 200 and not page.is_json and '<html' in page.get_data(as_text=True), (
            'full native page', url, page.status_code)

    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        event = Event.get(event_id)
        abstract = Abstract.get(abstract_id)
        track = Track(event=event, title='临时审稿专题', position=0)
        db.session.add(track)
        event.update_principal(User.get(user_ids[3]), add_permissions={'abstract_reviewer'})
        track.update_principal(User.get(user_ids[3]), add_permissions={'review'})
        abstract.reviewed_for_tracks.add(track)
        # Linked authors own a submission even when another account submitted it.
        coauthor = EventPerson(event=event, user=User.get(user_ids[3]), first_name='审稿人', last_name='coauthor',
                               email=f'workspace-business-reviewer-{suffix}@conference.test')
        db.session.add(coauthor)
        abstract.person_links.append(AbstractPersonLink(person=coauthor, author_type=AuthorType.secondary))
        db.session.flush()
        track_id = track.id
        db.session.commit()
    reviewer_data = reviewer.get('/api/participation/').json
    assert [record['id'] for record in reviewer_data['submissions']] == [abstract_id]
    assert reviewer_data['reviews'][0]['tracks'][0]['id'] == track_id
    assert reviewer_data['reviews'][0]['tracks'][0]['count'] == 1
    assert reviewer.get(reviewer_data['reviews'][0]['url']).status_code == 200
    assert reviewer.get(reviewer_data['reviews'][0]['tracks'][0]['url']).status_code == 200
    assert other.get('/api/participation/').json['reviews'] == []

    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        event = Event.get(event_id)
        event.update_principal(User.get(user_ids[2]), add_permissions={'registration'})
        User.get(user_ids[0]).is_admin = True
        db.session.commit()
    assert other.get(f'/api/conferences/{event_id}/operations').status_code == 403
    assert owner.get('/api/participation/').json['reviews'] == [], 'global administration is not assignment'
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        User.get(user_ids[0]).is_admin = False
        db.session.commit()

    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        Event.get(event_id).is_locked = True
        db.session.commit()
    locked = owner.get(f'/api/conferences/{event_id}/operations')
    assert locked.status_code == 200 and locked.json['event']['locked']
    assert not attendee.get('/api/participation/').json['registrations'][0]['can_modify']
    assert not attendee.get('/api/participation/').json['submissions'][0]['can_edit']
    assert owner.put(f'/api/conferences/{event_id}/content', json={
        'revision': saved.json['revision'], 'template': 'academic-full', 'content': payload['content']},
        headers={'X-CSRF-Token': owner_token}).status_code == 403
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        Event.get(event_id).is_locked = False
        Registration.get(registration_id).update_state(withdrawn=True)
        Abstract.get(abstract_id).state = AbstractState.withdrawn
        db.session.commit()
    own_withdrawn = attendee.get('/api/participation/').json
    assert own_withdrawn['registrations'][0]['state'] == 'withdrawn'
    assert own_withdrawn['submissions'][0]['state'] == 'withdrawn'
    assert own_withdrawn['registrations'][0]['ticket_url'] is None
    assert owner.get(f'/api/conferences/{event_id}/operations').json['submission']['counts']['withdrawn'] == 1
    assert owner.get(f'/event/{event_id}/manage/registration/{form_id}/registrations/').status_code == 200
    assert owner.get(f'/event/{event_id}/manage/abstracts/').status_code == 200
    assert owner.post(f'/api/conferences/{event_id}/publication', json={'published': False},
                      headers={'X-CSRF-Token': owner_token}).status_code == 200
    denied = attendee.get(f'/event/{event_id}/registrations/{form_id}/')
    assert denied.status_code == 403, ('withdrawal also blocks native registration pages', denied.status_code)
    assert attendee.get('/api/participation/').json == {'registrations': [], 'submissions': [], 'reviews': []}
    assert reviewer.get('/api/participation/').json == {'registrations': [], 'submissions': [], 'reviews': []}
    # Full management still permits the read-only dashboard of a withdrawn conference.
    assert owner.get(f'/api/conferences/{event_id}/operations').status_code == 200
    assert owner.post(f'/api/conferences/{event_id}/publication', json={'published': True},
                      headers={'X-CSRF-Token': owner_token}).status_code == 200
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        event = Event.get(event_id)
        set_feature_enabled(event, 'registration', False)
        set_feature_enabled(event, 'abstracts', False)
        db.session.commit()
    disabled = owner.get(f'/api/conferences/{event_id}/operations').json
    assert disabled['features'] == {'registration': False, 'abstracts': False}
    assert disabled['registration'] == {'enabled': False, 'total': 0, 'pending': 0, 'forms': [], 'links': {}}
    assert disabled['submission']['recent'] == [] and disabled['submission']['links'] == {}
    assert disabled['submission']['total'] == 0 and disabled['submission']['counts'] == {}
    assert owner.get(disabled['event']['feature_url']).status_code == 200
    assert attendee.get('/api/participation/').json == {'registrations': [], 'submissions': [], 'reviews': []}
    result = {'passed': True, 'native_registration_submitted': True, 'native_abstract_submitted': True,
              'organizer_can_view_records': True, 'withdrawal_blocks_attendee': True, 'mail_backend': 'memory',
              'private_api_isolation': True, 'linked_author': True, 'actual_review_task': True,
              'native_links_full_html': True, 'locked_read_only': True, 'disabled_features': True}
finally:
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        db.session.rollback()
        if event_id:
            event = Event.get(event_id)
            assert event.title.startswith('业务工作台验收 ')
            event.is_deleted = True
        for user_id in user_ids:
            user = User.get(user_id)
            assert user.email.startswith('workspace-business-') and user.email.endswith('@conference.test')
            user.is_admin = False
            user.is_deleted = True
        db.session.commit()
        assert User.query.filter(User.id.in_(user_ids), ~User.is_deleted).count() == 0
        assert not event_id or Event.get(event_id).is_deleted

print(json.dumps(result))


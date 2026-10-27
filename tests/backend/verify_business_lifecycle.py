"""Verify native registration approval/export and abstract review/judgment with locmem mail."""
import json
import os
import uuid
from datetime import timedelta

# Use the native validator's documented test-domain mode without external DNS or mail.
os.environ['PYTEST_CURRENT_TEST'] = 'verify_business_lifecycle'

from indico.web.flask.app import make_app
from indico.core.db import db
from indico.modules.auth import Identity
from indico.modules.users import User
from indico.modules.users.operations import create_user
from indico.modules.events import Event
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration
from indico.modules.events.registration.util import create_personal_data_fields
from indico.modules.events.abstracts.models.abstracts import Abstract, AbstractState
from indico.modules.events.abstracts.models.reviews import AbstractReview, AbstractAction
from indico.modules.events.tracks.models.tracks import Track
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
        for role in ('owner', 'attendee', 'reviewer'):
            name = f'business-lifecycle-{role}-{suffix}'
            user = create_user(name + '@conference.test', {'first_name': '流程验收', 'last_name': role},
                               Identity(provider='indico', identifier=name, password=uuid.uuid4().hex))
            db.session.flush()
            user_ids.append(user.id)
        db.session.commit()
    owner = app.test_client()
    owner_token = login(owner, user_ids[0])
    created = owner.post('/api/conferences/', json={
        'title': f'业务闭环验收 {suffix}', 'start': '2027-10-20T09:00', 'end': '2027-10-22T17:00',
        'location': '武汉', 'description': '临时会议，仅测试真实报名和投稿，不发送外部邮件。',
        'template': 'academic-full'}, headers={'X-CSRF-Token': owner_token})
    assert created.status_code == 201, ('complete template creation', created.status_code)
    event_id = created.json['id']
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
    assert attendee.get(f'/event/{event_id}/registrations/{form_id}/').status_code == 200
    submitted = attendee.post(f'/event/{event_id}/registrations/{form_id}/', json={
        'first_name': '流程验收', 'last_name': 'attendee',
        'email': f'business-lifecycle-attendee-{suffix}@conference.test', 'affiliation': '遇见科技'},
        headers={'X-CSRF-Token': attendee_token})
    assert submitted.status_code == 200 and 'redirect' in (submitted.json or {}), (
        'native registration submission', submitted.status_code, submitted.get_data(as_text=True)[:900])
    with app.app_context():
        registration = Registration.query.filter_by(registration_form_id=form_id, user_id=user_ids[1]).one()
        assert registration.first_name == '流程验收'
        registration_id = registration.id
    author = {'first_name': '流程验收', 'last_name': 'attendee', 'email': f'business-lifecycle-attendee-{suffix}@conference.test',
              'affiliation': '遇见科技', 'roles': ['primary', 'speaker']}
    abstract = attendee.post(f'/event/{event_id}/abstracts/submit', data={
        'title': '原生投稿端到端验收', 'description': '验证会议网站入口与原生摘要投稿记录相连。',
        'person_links': json.dumps([author]), 'csrf_token': attendee_token},
        headers={'X-CSRF-Token': attendee_token, 'X-Requested-With': 'XMLHttpRequest'})
    assert abstract.status_code == 200 and 'redirect' in (abstract.json or {}), (
        'native abstract submission', abstract.status_code, abstract.get_data(as_text=True)[:1100])
    with app.app_context():
        abstract_id = Abstract.query.filter_by(event_id=event_id, submitter_id=user_ids[1], title='原生投稿端到端验收').one().id
    pending = attendee.get('/api/participation/').json
    assert pending['registrations'][0]['state'] == 'pending'
    approved = owner.post(f'/event/{event_id}/manage/registration/{form_id}/registrations/{registration_id}/approve',
                          headers={'X-CSRF-Token': owner_token})
    assert approved.status_code == 200, ('native approval', approved.status_code)
    assert attendee.get('/api/participation/').json['registrations'][0]['state'] == 'complete'
    exported = owner.get(f'/event/{event_id}/manage/registration/{form_id}/registrations/registrations.csv')
    assert exported.status_code == 200, ('native CSV export', exported.status_code)
    assert 'attachment' in exported.headers.get('Content-Disposition', '')
    assert f'business-lifecycle-attendee-{suffix}@conference.test' in exported.get_data(as_text=True)
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        event = Event.get(event_id)
        track = Track(event=event, title='闭环审稿专题', position=0)
        db.session.add(track)
        event.update_principal(User.get(user_ids[2]), add_permissions={'abstract_reviewer'})
        track.update_principal(User.get(user_ids[2]), add_permissions={'review'})
        abstract_record = Abstract.get(abstract_id)
        abstract_record.reviewed_for_tracks.add(track)
        db.session.flush()
        track_id = track.id
        db.session.commit()
    reviewer = app.test_client()
    reviewer_token = login(reviewer, user_ids[2])
    tasks = reviewer.get('/api/participation/').json['reviews']
    assert tasks[0]['tracks'][0]['count'] == 1
    review = reviewer.post(f'/event/{event_id}/abstracts/{abstract_id}/review/track/{track_id}', data={
        f'track-{track_id}-proposed_action': 'accept', f'track-{track_id}-comment': '真实评审操作验收：建议录用。',
        f'track-{track_id}-csrf_token': reviewer_token},
        headers={'X-CSRF-Token': reviewer_token, 'X-Requested-With': 'XMLHttpRequest'})
    assert review.status_code == 200 and review.is_json, ('native review', review.status_code, review.get_data(as_text=True)[:1200])
    with app.app_context():
        review_record = AbstractReview.query.filter_by(abstract_id=abstract_id, user_id=user_ids[2], track_id=track_id).one()
        assert review_record.proposed_action == AbstractAction.accept
    assert reviewer.get('/api/participation/').json['reviews'] == [], 'Submitted review must clear the pending review task before judgment'
    judged = owner.post(f'/event/{event_id}/manage/abstracts/{abstract_id}/judge', data={
        'judgment': 'accept', 'accepted_track': str(track_id), 'judgment_comment': '流程验收录用。',
        'csrf_token': owner_token}, headers={'X-CSRF-Token': owner_token, 'X-Requested-With': 'XMLHttpRequest'})
    assert judged.status_code == 200 and judged.is_json, ('native judgment', judged.status_code, judged.get_data(as_text=True)[:1200])
    with app.app_context():
        accepted = Abstract.get(abstract_id)
        assert accepted.state == AbstractState.accepted and accepted.contribution is not None
    assert attendee.get('/api/participation/').json['submissions'][0]['state'] == 'accepted'
    assert reviewer.get('/api/participation/').json['reviews'] == []
    overview = owner.get(f'/api/conferences/{event_id}/operations').json
    assert overview['registration']['total'] == 1 and overview['registration']['pending'] == 0
    assert overview['submission']['counts'] == {'accepted': 1} and overview['submission']['pending'] == 0
    assert owner.get(f'/event/{event_id}/manage/registration/{form_id}/registrations/').status_code == 200
    assert owner.get(f'/event/{event_id}/manage/abstracts/').status_code == 200
    assert owner.post(f'/api/conferences/{event_id}/publication', json={'published': False},
                      headers={'X-CSRF-Token': owner_token}).status_code == 200
    denied = attendee.get(f'/event/{event_id}/registrations/{form_id}/')
    assert denied.status_code == 403, ('withdrawal also blocks native registration pages', denied.status_code)
    result = {'passed': True, 'native_registration_submitted': True, 'native_abstract_submitted': True,
              'registration_approved': True, 'csv_exported': True, 'review_submitted': True,
              'abstract_accepted_with_contribution': True, 'workspace_states_synchronized': True,
              'organizer_can_view_records': True, 'withdrawal_blocks_attendee': True, 'mail_backend': 'memory'}
finally:
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        db.session.rollback()
        if event_id:
            event = Event.get(event_id)
            assert event.title.startswith('业务闭环验收 ')
            event.is_deleted = True
        for user_id in user_ids:
            user = User.get(user_id)
            assert user.email.startswith('business-lifecycle-') and user.email.endswith('@conference.test')
            user.is_deleted = True
        db.session.commit()

print(json.dumps(result))

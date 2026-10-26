"""Exercise the real HTTP/model flow with disposable ordinary accounts; no external mail."""
import json
import uuid
from unittest.mock import patch

from indico.web.flask.app import make_app
from indico.core.db import db
from indico.modules.auth import Identity
from indico.modules.users import User
from indico.modules.users.operations import create_user
from indico.modules.events import Event
from indico.modules.events.layout.models.menu import MenuEntry, MenuEntryType
from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.attachments.models.attachments import Attachment, AttachmentType
from indico.modules.attachments.models.folders import AttachmentFolder

app = make_app(config_override={'EMAIL_BACKEND': 'indico.vendor.django_mail.backends.locmem.EmailBackend',
                                'SMTP_USE_CELERY': False})
app.config['REPL'] = True
app.config['TESTING'] = True
suffix = uuid.uuid4().hex[:10]
users = []
event_ids = []

def login(client, user):
    with client.session_transaction() as sess:
        sess.set_session_user(user)
    return json.loads(client.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']

try:
    client = app.test_client()
    email = f'fixture-owner-{suffix}@example.invalid'
    username = f'fixture-owner-{suffix}'
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        from indico.util.signing import secure_serializer
        verification_token = secure_serializer.dumps(email, salt='register-email')
    assert client.get('/register/?token=invalid').status_code == 400
    assert client.get('/register/', query_string={'token': verification_token}).status_code == 302
    csrf = json.loads(client.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']
    registered = client.post('/register/', json={'email': email, 'username': username,
                             'password': uuid.uuid4().hex + '!Q8', 'first_name': '建站验收',
                             'last_name': 'owner', 'affiliation': '遇见科技'},
                             headers={'X-CSRF-Token': csrf})
    assert registered.status_code == 200 and 'redirect' in registered.json, registered.get_data(as_text=True)[:200]
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        users.append(Identity.query.filter_by(provider='indico', identifier=username).one().user)
        for name in ('other',):
            user = create_user(f'fixture-{name}-{suffix}@example.invalid',
                               {'first_name': '建站验收', 'last_name': name},
                               Identity(provider='indico', identifier=f'fixture-{name}-{suffix}', password=uuid.uuid4().hex))
            users.append(user)
        db.session.commit()
        ids = [u.id for u in users]
    with app.app_context():
        token = login(client, User.get(ids[0]))
    data = {'title': f'一键建站验收 {suffix}', 'start': '2027-06-10T09:00', 'end': '2027-06-12T17:00',
            'location': '武汉', 'description': '<script>unsafe</script>学术交流', 'template': 'industry'}
    response = client.post('/api/conferences/', json=data, headers={'X-CSRF-Token': token})
    assert response.status_code == 201, (response.status_code, response.get_data(as_text=True)[:200])
    event_id = response.json['id']; event_ids.append(event_id)
    assert response.json['published'] is False
    assert client.get('/api/organizer/conferences/').json['events'][0]['id'] == event_id
    anon = app.test_client()
    assert anon.get('/api/conferences/?page=invalid').status_code == 400
    assert anon.get('/api/conferences/?page=99999999999999999999999999').status_code == 400
    assert event_id not in [e['id'] for e in anon.get('/api/conferences/').json['events']]
    assert anon.get(f'/event/{event_id}/').status_code != 200
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        from yujian_site import YujianSitePlugin
        event = Event.get(event_id)
        assert not event.creator.is_admin and event.category.can_create_events(event.creator)
        assert not event.category.can_manage(event.creator)
        pages = MenuEntry.query.filter_by(event_id=event_id, type=MenuEntryType.page).all()
        assert len(pages) == 6
        YujianSitePlugin.instance.initialize(event)
        assert MenuEntry.query.filter_by(event_id=event_id, type=MenuEntryType.page).count() == 6
        assert '<script>' not in str(event.description)
        page_id = pages[0].page_id
    other = app.test_client()
    with app.app_context():
        other_token = login(other, User.get(ids[1]))
    assert other.post(f'/api/conferences/{event_id}/publication', json={'published': True},
                      headers={'X-CSRF-Token': other_token}).status_code == 403
    assert other.get(f'/conference/{event_id}/').status_code == 403
    assert client.post(f'/api/conferences/{event_id}/publication', json={'published': True}).status_code == 400
    bad = client.post('/api/conferences/', json=data | {'end': data['start']}, headers={'X-CSRF-Token': token})
    assert bad.status_code == 400
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        Event.get(event_id).is_locked = True
        db.session.commit()
    assert client.post(f'/api/conferences/{event_id}/publication', json={'published': True},
                       headers={'X-CSRF-Token': token}).status_code == 403
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        Event.get(event_id).is_locked = False
        db.session.commit()
    published = client.post(f'/api/conferences/{event_id}/publication', json={'published': True},
                            headers={'X-CSRF-Token': token})
    assert published.status_code == 200
    assert event_id in [e['id'] for e in anon.get('/api/conferences/').json['events']]
    assert anon.get(f'/event/{event_id}/').status_code == 200
    assert anon.get(f'/event/{event_id}/page/{page_id}').status_code == 200
    # The redesigned views must retain native page permissions and default-home behavior.
    assert b'data-mode="directory"' in anon.get('/category/1/').data
    assert b'data-mode="organizer"' in client.get('/user/dashboard/').data
    assert b'meet-workspace' not in client.get('/user/dashboard/?legacy=1').data
    assert event_id not in [e['id'] for e in other.get('/api/organizer/conferences/').json['events']]
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        event = Event.get(event_id)
        event.update_principal(User.get(ids[1]), full_access=True)
        notices = MenuEntry.query.filter_by(event_id=event_id, title='重要通知').one()
        notices.protection_mode = ProtectionMode.protected
        notices.update_principal(User.get(ids[0]), read_access=True)
        notices.page.html = '<p>PRIVATE-NOTICE-ACL</p><script>alert("UNSAFE-PAGE")</script>'
        notice_url = notices.url
        event.default_page = MenuEntry.query.filter_by(event_id=event_id, title='会议委员会').one().page
        event.default_page.html = '<p>DEFAULT-HOME-CONTENT</p>'
        db.session.commit()
    assert event_id in [e['id'] for e in other.get('/api/organizer/conferences/').json['events']]
    assert b'conference-rich-text' in anon.get(f'/event/{event_id}/').data
    assert b'DEFAULT-HOME-CONTENT' in anon.get(f'/event/{event_id}/').data
    overview = anon.get(f'/event/{event_id}/overview')
    assert overview.status_code == 200
    assert b'PRIVATE-NOTICE-ACL' not in overview.data and b'DEFAULT-HOME-CONTENT' not in overview.data
    denied_notice = anon.get(notice_url)
    assert denied_notice.status_code == 403 or (denied_notice.status_code == 302 and '/login/' in denied_notice.location)
    own_notice_response = client.get(notice_url, follow_redirects=True)
    own_notice = own_notice_response.data
    assert b'PRIVATE-NOTICE-ACL' in own_notice and b'<script>alert(' not in own_notice, (
        own_notice_response.status_code, b'PRIVATE-NOTICE-ACL' in own_notice, b'<script>alert(' in own_notice)
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        from indico.modules.events.layout import layout_settings
        from indico.modules.events.layout.util import get_css_url
        event = Event.get(event_id)
        event.stylesheet = '.conf { color: #123456; }'
        event.stylesheet_metadata = {'hash': 'abcdef12', 'size': len(event.stylesheet), 'filename': 'fixture.css'}
        layout_settings.set(event, 'use_custom_css', True)
        custom_css_url = get_css_url(event)
        db.session.commit()
    themed_home = anon.get(f'/event/{event_id}/')
    assert themed_home.status_code == 200
    assert b'conference-banner-inner' not in themed_home.data and custom_css_url.encode() in themed_home.data
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        event = Event.get(event_id)
        layout_settings.set(event, 'use_custom_css', False)
        event.update_principal(User.get(ids[1]), full_access=False)
        event.default_page = None
        db.session.commit()
    assert event_id not in [e['id'] for e in other.get('/api/organizer/conferences/').json['events']]
    export_url = f'/export/event/{event_id}.json?from=2020-01-01&to=2030-01-01'
    assert len(anon.get(export_url).json['results']) == 1
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        event = Event.get(event_id)
        folder = AttachmentFolder(object=event, title='验收资料', protection_mode=ProtectionMode.protected)
        folder.update_principal(User.get(ids[1]), read_access=True)
        attachment = Attachment(folder=folder, user=User.get(ids[0]), type=AttachmentType.link,
                                title='保护链接', link_url='https://example.invalid/fixture',
                                protection_mode=ProtectionMode.protected)
        attachment.update_principal(User.get(ids[1]), read_access=True)
        db.session.add_all([folder, attachment]); db.session.flush()
        attachment_id, folder_id = attachment.id, folder.id
        attachment_url = attachment.download_url
        assert attachment.can_access(User.get(ids[1]))
        db.session.commit()
    assert other.get(attachment_url).status_code == 302
    result = client.post(f'/api/conferences/{event_id}/publication', json={'published': False},
                         headers={'X-CSRF-Token': token})
    assert result.status_code == 200
    assert event_id not in [e['id'] for e in anon.get('/api/conferences/').json['events']]
    assert anon.get(f'/event/{event_id}/').status_code != 200
    assert not anon.get(export_url).json.get('results', [])
    assert other.get(attachment_url).status_code == 403
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        event = Event.get(event_id)
        event.update_principal(User.get(ids[1]), read_access=True)
        db.session.flush()
        assert not event.can_access(User.get(ids[1])), 'A read-only ACL must not expose a draft'
        assert not Attachment.get(attachment_id).can_access(User.get(ids[1]))
        assert not AttachmentFolder.get(folder_id).can_access(User.get(ids[1]))
        from yujian_site.legacy import WebsiteFileHook
        hook = WebsiteFileHook.__new__(WebsiteFileHook)
        hook._attachment = Attachment.get(attachment_id)
        with patch('indico.web.http_api.hooks.file.FileHook._has_access', return_value=True):
            assert not hook._has_access(User.get(ids[1])), 'Legacy files must check draft state before resource roles'
        db.session.commit()
    result = {'passed': True, 'native_registration_with_test_token': True, 'invalid_token_rejected': True,
                      'ordinary_account_create': True, 'pages': 6, 'idempotent': True,
                      'draft_private': True, 'cross_account_denied': True, 'csrf_required': True,
                      'validation': True, 'publish_list_and_site': True, 'withdraw_private': True,
                      'locked_event_denied': True, 'withdraw_export_private': True,
                      'read_acl_draft_denied': True, 'pagination_validation': True,
                      'attachment_withdraw_denied': True, 'legacy_file_role_bypass_denied': True,
                      'modern_entry_points': True, 'delegated_management_list': True,
                      'private_page_excerpts_denied': True, 'default_home_preserved': True, 'page_html_sanitized': True,
                      'explicit_native_css_preserved': True,
                      'external_email_sent': False}
finally:
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        for event_id in event_ids:
            Event.get(event_id).is_deleted = True
        for user in users:
            current = User.get(user.id)
            if current:
                current.is_deleted = True
        db.session.commit()
print(json.dumps(result))

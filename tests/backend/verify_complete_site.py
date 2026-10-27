"""Real Indico integration checks with disposable fixtures and no outbound mail."""
import copy
import io
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

from PIL import Image
from indico.web.flask.app import make_app
from indico.core.db import db
from indico.modules.auth import Identity
from indico.modules.users import User
from indico.modules.users.operations import create_user
from indico.modules.events import Event
from indico.modules.events.layout.models.menu import MenuEntry, MenuEntryType
from indico.modules.events.models.settings import EventSetting
from indico.modules.attachments.models.attachments import Attachment, AttachmentFile, AttachmentType
from indico.modules.attachments.models.folders import AttachmentFolder
from indico.core.db.sqlalchemy.protection import ProtectionMode

app = make_app(config_override={'EMAIL_BACKEND': 'indico.vendor.django_mail.backends.locmem.EmailBackend',
                                'SMTP_USE_CELERY': False})
app.config.update(REPL=True, TESTING=True)
suffix = uuid.uuid4().hex[:10]
users, event_ids = [], []


def login(client, user):
    with client.session_transaction() as sess:
        sess.set_session_user(user)
    return json.loads(client.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']


def check(response, status):
    assert response.status_code == status, (response.status_code, response.get_data(as_text=True)[:160])
    return response


try:
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        for role in ('owner', 'other'):
            user = create_user(f'complete-{role}-{suffix}@example.invalid',
                               {'first_name': 'Complete fixture', 'last_name': role},
                               Identity(provider='indico', identifier=f'complete-{role}-{suffix}', password=uuid.uuid4().hex))
            users.append(user.id)
        db.session.commit()
    client, other, anon = app.test_client(), app.test_client(), app.test_client()
    with app.app_context():
        token = login(client, User.get(users[0]))
        other_token = login(other, User.get(users[1]))
    headers = {'X-CSRF-Token': token}
    create_data = {'title': f'完整会议验收 {suffix}', 'start': '2027-06-10T09:00', 'end': '2027-06-12T17:00',
                   'location': '武汉', 'description': '真实学术交流'}
    legacy = check(client.post('/api/conferences/', json=create_data | {'template': 'industry'}, headers=headers), 201).json['id']
    event_ids.append(legacy)
    # First TDD run failed here with native catchall 405, proving the missing endpoint.
    legacy_payload = check(client.get(f'/api/conferences/{legacy}/content'), 200).json
    assert legacy_payload['revision'] == 0 and legacy_payload['template'] == 'industry'
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        assert EventSetting.query.filter_by(event_id=legacy, module='plugin_yujian_site', name='content').count() == 0
        assert MenuEntry.query.filter_by(event_id=legacy, type=MenuEntryType.page).count() == 6
    event_id = check(client.post('/api/conferences/', json=create_data, headers=headers), 201).json['id']
    event_ids.append(event_id)
    url = f'/api/conferences/{event_id}/content'
    payload = check(client.get(url), 200).json
    assert payload['template'] == 'academic-full' and payload['revision'] == 0
    assert payload['content']['speakers'] == [] and payload['content']['news'] == []
    assert len(payload['content']['organizations']) == 4 and payload['content']['dates']
    assert payload['registration_url'] == f'/event/{event_id}/registrations/'
    assert payload['submission_url'] == f'/event/{event_id}/abstracts/'
    assert check(client.get(url), 200).headers['Cache-Control'] == 'private, no-store'
    assert anon.get(url).status_code == 401 and other.get(url).status_code == 403
    check(client.put(url, json=payload), 400)
    content = copy.deepcopy(payload['content'])
    content['banner'].update(title='中文横幅', title_en='English banner')
    content['speakers'] = [{'name': '临时嘉宾', 'name_en': 'Fixture speaker', 'enabled': True}]
    content['news'] = [{'title': '会议消息', 'body': '纯文本<script>不会执行</script>', 'enabled': False}]
    content['sections'].reverse()
    saved = check(client.put(url, json={'revision': 0, 'template': 'academic-full', 'content': content}, headers=headers), 200).json
    assert saved['revision'] == 1 and saved['content']['banner']['title_en'] == 'English banner'
    assert saved['content']['sections'][0]['key'] == content['sections'][0]['key'] and saved['content']['news'][0]['enabled'] is False
    check(client.put(url, json={'revision': 0, 'content': content}, headers=headers), 409)
    check(client.put(url, json={'revision': 1, 'content': content}), 400)
    check(other.put(url, json={'revision': 1, 'content': content},
                    headers={'X-CSRF-Token': other_token}), 403)
    for invalid in ({'unknown': True}, {'speakers': [{'name': 'Missing enabled'}]},
                    {'banner': {'show_title': 'true'}}, {'theme': {'accent': 'red;display:none'}},
                    {'actions': {'registration': {'mode': 'external', 'url': '//evil.invalid'}}},
                    {'actions': {'registration': {'mode': 'external', 'url': 'javascript:alert(1)'}}},
                    {'banner': {'image': '/event/22/attachments/1/1/fake.png'}},
                    {'news': [{'title': 'unsafe', 'url': '/%2f%2fevil.invalid', 'enabled': True}]}):
        check(client.put(url, json={'revision': 1, 'content': invalid}, headers=headers), 400)
    assets = f'/api/conferences/{event_id}/assets'
    def upload(data, filename='fixture.png', client_=client, token_=token):
        return client_.post(assets, data={'file': (io.BytesIO(data), filename)},
                            headers={'X-CSRF-Token': token_}, content_type='multipart/form-data')
    check(upload(b'<svg xmlns="http://www.w3.org/2000/svg"/>', 'fixture.svg'), 400)
    check(upload(b'not an image'), 400)
    check(upload(b'x' * (5 * 1024 * 1024 + 1)), 400)
    oversized = io.BytesIO()
    Image.new('1', (5000, 4001)).save(oversized, format='PNG')
    check(upload(oversized.getvalue()), 400)
    image = io.BytesIO(); Image.new('RGB', (4, 3), '#ff7d4b').save(image, format='PNG')
    check(upload(image.getvalue(), client_=other, token_=other_token), 403)
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        from yujian_site.site_content import ASSET_FOLDER
        from indico.modules.events.sessions.models.sessions import Session
        event = Event.get(event_id)
        native_session = Session(event=event, title='Session asset fixture')
        session_folder = AttachmentFolder(object=native_session, title=ASSET_FOLDER,
                                           is_hidden=True, is_always_visible=False,
                                           protection_mode=ProtectionMode.inheriting)
        session_image = Attachment(folder=session_folder, user=User.get(users[0]),
                                   title='Session image', type=AttachmentType.file)
        session_image.file = AttachmentFile(user=User.get(users[0]), filename='session.png', content_type='image/png')
        session_image.file.save(io.BytesIO(image.getvalue()))
        db.session.add_all([native_session, session_image]); db.session.flush()
        session_asset_url = session_image.download_url
        collision_folder = AttachmentFolder(object=Event.get(event_id), title=ASSET_FOLDER,
                                             is_hidden=False, is_always_visible=True,
                                             protection_mode=ProtectionMode.protected)
        db.session.add(collision_folder); db.session.flush()
        collision_folder_id = collision_folder.id
        db.session.commit()
    check(client.put(url, json={'revision': 1, 'content': {'banner': {'image': session_asset_url}}}, headers=headers), 400)
    asset = check(upload(image.getvalue(), 'wrong-extension.svg'), 201).json['url']
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        attachment = next(a for a in Attachment.query.join(Attachment.folder).filter(
            AttachmentFolder.event_id == event_id).all() if a.download_url == asset)
        assert attachment.folder_id != collision_folder_id, 'Upload must not reuse an owner visible folder with the reserved title'
        assert attachment.folder.is_hidden and not attachment.folder.is_always_visible
        assert attachment.folder.protection_mode == ProtectionMode.inheriting
        assert attachment.folder.object == Event.get(event_id)
        collision_folder = AttachmentFolder.get(collision_folder_id)
        assert not collision_folder.is_hidden and collision_folder.is_always_visible
        assert collision_folder.protection_mode == ProtectionMode.protected
    for format_, extension in [('JPEG', 'jpg'), ('WEBP', 'webp')]:
        variant = io.BytesIO(); Image.new('RGB', (4, 3)).save(variant, format=format_)
        check(upload(variant.getvalue(), f'fixture.{extension}'), 201)
    check(client.put(f'/api/conferences/{legacy}/content',
                     json={'revision': 0, 'content': {'banner': {'image': asset}}}, headers=headers), 400)
    assert check(client.get(url), 200).json['revision'] == 1
    content['banner']['image'] = asset
    check(client.put(url, json={'revision': 1, 'content': content}, headers=headers), 200)
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        from indico.modules.events.features.util import is_feature_enabled
        from indico.modules.events.registration.models.forms import RegistrationForm
        event = Event.get(event_id)
        assert is_feature_enabled(event, 'registration') and is_feature_enabled(event, 'abstracts')
        assert RegistrationForm.query.filter_by(event_id=event_id).count() == 0
        navigation = MenuEntry.query.filter_by(event_id=event_id, parent_id=None, is_enabled=True).order_by(MenuEntry.position).all()
        assert [entry.title for entry in navigation] == ['会议首页', '会议组织', '会议日程', '注册缴费', '会议投稿',
                                                        '会议酒店', '考察活动', '历届会议', '联系我们']
        pages = MenuEntry.query.filter_by(event_id=event_id, type=MenuEntryType.page).all()
        organization = next(p for p in pages if p.title == '会议组织')
        assert {p.title for p in organization.children} == {'组委会', '专题召集人'}
        original = next(p for p in pages if p.title == '会议主题')
        original.page.html = '<p>OWNER CONTENT PRESERVED</p>'
        page_count = len(pages)
        event.is_locked = True
        db.session.commit()
    check(client.get(url), 200)  # Native locks allow reads and reject modifications.
    check(client.put(url, json={'revision': 2, 'content': content}, headers=headers), 403)
    check(upload(image.getvalue()), 403)
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        Event.get(event_id).is_locked = False
        db.session.commit()
    check(client.put(url, json={'revision': 2, 'content': content}, headers=headers), 200)
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        assert MenuEntry.query.filter_by(event_id=event_id, type=MenuEntryType.page).count() == page_count
        assert 'OWNER CONTENT PRESERVED' in MenuEntry.query.filter_by(event_id=event_id, title='会议主题').one().page.html
    concurrent_clients = [app.test_client(), app.test_client()]
    with app.app_context():
        concurrent_tokens = [login(c, User.get(users[0])) for c in concurrent_clients]
    def concurrent_save(pair):
        c, csrf = pair
        return c.put(url, json={'revision': 3, 'content': content}, headers={'X-CSRF-Token': csrf}).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(concurrent_save, zip(concurrent_clients, concurrent_tokens)))
    assert sorted(statuses) == [200, 409], statuses
    assert check(client.get(url), 200).json['revision'] == 4
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        legacy_entry = MenuEntry.query.filter_by(event_id=legacy, title='会议委员会').one()
        legacy_entry.page.html = '<p>LEGACY OWNER CONTENT</p>'
        legacy_positions = {entry.id: (entry.position, entry.is_enabled) for entry in
                            MenuEntry.query.filter_by(event_id=legacy).all()}
        db.session.commit()
    check(client.put(f'/api/conferences/{legacy}/content',
                     json={'revision': 0, 'content': legacy_payload['content'], 'template': 'academic-full'}, headers=headers), 200)
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        assert 'LEGACY OWNER CONTENT' in MenuEntry.query.filter_by(event_id=legacy, title='会议委员会').one().page.html
        assert all((entry.position, entry.is_enabled) == legacy_positions[entry.id]
                   for entry in MenuEntry.query.filter_by(event_id=legacy).all() if entry.id in legacy_positions)
    check(client.post(f'/api/conferences/{event_id}/publication', json={'published': True}, headers=headers), 200)
    check(anon.get(asset), 200)
    check(anon.get(payload['registration_url']), 200)
    assert anon.get(payload['submission_url']).status_code in (200, 302)
    check(client.post(f'/api/conferences/{event_id}/publication', json={'published': False}, headers=headers), 200)
    assert anon.get(asset).status_code != 200
    result = {'passed': True, 'legacy_defaults_nonpersistent': True, 'native_pages_preserved': True,
              'content_revision_and_conflict': True, 'concurrent_revision_lock': True,
              'acl_csrf_lock': True, 'validation': True, 'cross_event_image_rejected': True,
              'visible_folder_collision_preserved': True,
              'real_image_upload': True, 'attachment_withdraw_private': True, 'native_features_closed': True,
              'external_email_sent': False}
finally:
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        db.session.rollback()
        for event_id in event_ids:
            Event.get(event_id).is_deleted = True
        for user_id in users:
            User.get(user_id).is_deleted = True
        db.session.commit()
print(json.dumps(result))

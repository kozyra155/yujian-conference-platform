"""Real appearance API checks using disposable ordinary accounts and local mail."""
import copy
import json
import uuid

from indico.web.flask.app import make_app
from indico.core.db import db
from indico.modules.auth import Identity
from indico.modules.users import User
from indico.modules.users.operations import create_user
from indico.modules.events import Event
from indico.modules.events.layout.models.menu import EventPage, MenuEntry
from indico.modules.events.models.settings import EventSetting

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
    assert response.status_code == status, (response.status_code, response.get_data(as_text=True)[:200])
    return response


def snapshot(event_id):
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        settings = dict(db.session.query(EventSetting.name, EventSetting.value).filter_by(
            event_id=event_id, module='plugin_yujian_site').all())
        menus = [(m.id, m.parent_id, m.position, m.is_enabled, m.title, m.page_id)
                 for m in MenuEntry.query.filter_by(event_id=event_id).order_by(MenuEntry.id)]
        pages = [(p.id, str(p.html)) for p in EventPage.query.filter_by(event_id=event_id).order_by(EventPage.id)]
        return copy.deepcopy((settings, menus, pages))


try:
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        for role in ('owner', 'other'):
            user = create_user(f'appearance-{role}-{suffix}@example.invalid',
                               {'first_name': 'Appearance fixture', 'last_name': role},
                               Identity(provider='indico', identifier=f'appearance-{role}-{suffix}', password=uuid.uuid4().hex))
            users.append(user.id)
        db.session.commit()
    client, other, anon = app.test_client(), app.test_client(), app.test_client()
    with app.app_context():
        token = login(client, User.get(users[0]))
        other_token = login(other, User.get(users[1]))
    headers = {'X-CSRF-Token': token}
    create_data = {'title': f'外观验收 {suffix}', 'start': '2027-06-10T09:00', 'end': '2027-06-12T17:00',
                   'location': '武汉', 'description': '外观验收会议内容', 'template': 'academic'}
    event_id = check(client.post('/api/conferences/', json=create_data, headers=headers), 201).json['id']
    event_ids.append(event_id)
    url = f'/api/conferences/{event_id}/content'
    preview_url = f'/api/conferences/{event_id}/appearance-preview'
    before = snapshot(event_id)
    payload = check(client.get(url), 200).json
    assert 'appearances' in payload, 'Missing appearance catalog in content API'
    catalog = payload['appearances']
    colors = {'orange': '#fa7d4b', 'red': '#d94a45', 'purple': '#8550ad',
              'blue': '#3f67c8', 'navy': '#293d78', 'green': '#488b35'}
    assert len(catalog) == 12
    assert {a['id'] for a in catalog} == {f'{layout}-{color}' for layout in ('simple-1', 'simple-2') for color in colors}
    for appearance in catalog:
        assert set(appearance) == {'id', 'name', 'name_en', 'layout', 'accent'}
        assert appearance['name'] and appearance['name_en']
        assert appearance['accent'] == colors[appearance['id'].rsplit('-', 1)[1]]
        assert appearance['layout'] == appearance['id'].rsplit('-', 1)[0]
    assert payload['content']['theme'] == {'layout': 'simple-1', 'accent': '#fa7d4b'}
    assert snapshot(event_id) == before, 'Reading legacy defaults must not persist them'
    theme = {'layout': 'simple-2', 'accent': '#8550ad'}
    preview = check(client.post(preview_url, json={'theme': theme}, headers=headers), 200)
    assert preview.mimetype == 'text/html' and preview.headers['Cache-Control'] == 'private, no-store'
    assert 'appearance-simple-2' in preview.text and '#8550ad' in preview.text
    assert '外观验收会议内容' in preview.text
    assert snapshot(event_id) == before, ('Preview must not change legacy template, revision, pages, or menus',
                                          before, snapshot(event_id))
    anon_token = json.loads(anon.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']
    check(anon.post(preview_url, json={'theme': theme}, headers={'X-CSRF-Token': anon_token}), 401)
    check(other.post(preview_url, json={'theme': theme}, headers={'X-CSRF-Token': other_token}), 403)
    check(client.post(preview_url, json={'theme': theme}), 400)
    invalid_themes = [None, [], {'layout': 'simple-3'}, {'layout': 'simple-1 onload=alert(1)'},
                      {'layout': None}, {'layout': ['simple-1']}, {'accent': 'red'},
                      {'accent': '#123456;display:none'}, {'accent': '#123456\n'}, {'accent': 123456},
                      {'accent': '#123456', 'unknown': True}]
    for invalid in invalid_themes:
        check(client.post(preview_url, json={'theme': invalid}, headers=headers), 400)
        check(client.put(url, json={'revision': 0, 'content': {'theme': invalid}}, headers=headers), 400)
    for invalid_body in ({}, {'theme': theme, 'template': 'academic-full'}, {'theme': theme, 'content': {}}):
        check(client.post(preview_url, json=invalid_body, headers=headers), 400)
    assert snapshot(event_id) == before
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        Event.get(event_id).is_locked = True
        db.session.commit()
    check(client.post(preview_url, json={'theme': theme}, headers=headers), 403)
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        Event.get(event_id).is_locked = False
        db.session.commit()
    # Simulate an existing old-client save with no layout; defaults stay read-only.
    check(client.put(url, json={'revision': 0, 'content': {'theme': {'accent': '#AABBCC'}}}, headers=headers), 200)
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        from yujian_site import YujianSitePlugin
        event = Event.get(event_id)
        old_content = YujianSitePlugin.event_settings.get(event, 'content')
        old_content['theme'] = {'accent': '#aabbcc'}
        YujianSitePlugin.event_settings.set(event, 'content', old_content)
        db.session.commit()
    old_before = snapshot(event_id)
    legacy = check(client.get(url), 200).json
    assert legacy['content']['theme'] == {'layout': 'simple-1', 'accent': '#aabbcc'}
    assert snapshot(event_id) == old_before
    revision = legacy['revision']
    # Save each preset through the ordinary revision-protected content endpoint.
    content = copy.deepcopy(legacy['content'])
    content['banner']['title'] = 'PRESERVE OWNER BANNER'
    for appearance in catalog:
        content['theme'] = {k: appearance[k] for k in ('layout', 'accent')}
        saved = check(client.put(url, json={'revision': revision, 'content': content,
                                           'template': 'academic-full'}, headers=headers), 200).json
        revision += 1
        assert saved['revision'] == revision and saved['content'] == content
        with app.test_request_context(base_url='http://192.168.2.36:12880'):
            stored = EventSetting.query.filter_by(event_id=event_id, module='plugin_yujian_site', name='content').one().value
            assert stored['theme'] == content['theme']
        saved_before = snapshot(event_id)
        preview = check(client.post(preview_url, json={'theme': theme}, headers=headers), 200)
        assert 'appearance-simple-2' in preview.text and 'PRESERVE OWNER BANNER' in preview.text
        assert snapshot(event_id) == saved_before
    result = {'passed': True, 'catalog': 12, 'all_presets_saved': True, 'legacy_defaults_nonpersistent': True,
              'preview_no_writes': True, 'legacy_preview_template_unchanged': True, 'validation': True,
              'acl_csrf_lock': True, 'external_email_sent': False}
finally:
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        db.session.rollback()
        for event_id in event_ids:
            Event.get(event_id).is_deleted = True
        for user_id in users:
            User.get(user_id).is_deleted = True
        db.session.commit()
print(json.dumps(result))

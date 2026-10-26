"""Read-only extension contract checks; isolated app, no event or account writes."""
import copy
import io
import json
import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from werkzeug.exceptions import BadRequest
from PIL import Image
from indico.core.db import db
from indico.modules.auth import Identity
from indico.modules.users import User
from indico.modules.users.operations import create_user
from indico.modules.events import Event
from indico.modules.events.models.settings import EventSetting
from indico.web.flask.app import make_app
from yujian_site import YujianSitePlugin, display, site_content as sc

app = make_app(config_override={'EMAIL_BACKEND': 'indico.vendor.django_mail.backends.locmem.EmailBackend',
                                'SMTP_USE_CELERY': False})
app.config.update(TESTING=True)
event = SimpleNamespace(id=999999, title='Feedback fixture', start_dt_local=datetime(2027, 1, 1),
                        end_dt_local=datetime(2027, 1, 2), description='<p>Native introduction</p>',
                        venue_name='Fixture venue', timezone='Asia/Shanghai', can_manage=lambda user: False,
                        has_feature=lambda name: False, has_logo=False)
image = '/event/999999/attachments/fixture.png'

def bad(data, path):
    try:
        sc.validate_content(event, data)
    except BadRequest as error:
        assert path in error.description, (path, error.description)
        assert any('\u4e00' <= c <= '\u9fff' for c in error.description)
    else:
        raise AssertionError(f'{path} accepted invalid content')

with app.test_request_context(base_url='http://192.168.2.36:12880'), patch.object(sc, '_image_urls', return_value={image}):
    for safe_link in ('https://example.invalid/path%20name', 'https://example.invalid/path%20',
                      'mailto:team@example.invalid?subject=Hello%20team'):
        sc._safe_url(safe_link, allow_mailto=True)
    defaults = sc.default_content(event)
    assert 'committees' in defaults, 'Structured homepage sections must exist'
    assert {'registration_info', 'submission_info'} <= set(sc.SECTIONS), 'Instructions must be independent homepage sections'
    rich = sc.validate_content(event, {'contact': {'html': '<p>Preserved contact text</p><table><tr><td>Cell</td></tr></table>'
        '<a href="https://example.invalid/info">Contact link</a>'
        '<img src="https://external.example.invalid/image.png"><img src="/event/888888/attachments/foreign.png">'
        '<video src="https://external.example.invalid/movie.mp4"><source src="/event/888888/attachments/foreign.mp4"></video>'
        '<iframe src="https://external.example.invalid/embed"></iframe>'}})['contact']['html']
    assert '<img' not in rich and '<video' not in rich and '<source' not in rich and '<iframe' not in rich, 'Rich contact media must use the owned upload gallery'
    assert all(text in rich for text in ('Preserved contact text', '<table>', '<td>Cell</td>', 'href="https://example.invalid/info"'))
    assert all(not row['enabled'] for row in defaults['sections'] if row['key'] not in ('introduction', 'speakers', 'news', 'notices', 'venue'))
    legacy = {'sections': [{'key': 'venue', 'enabled': True}], 'speakers': [{'name': 'Old speaker', 'enabled': True}],
              'actions': {'registration': {'enabled': True}}, 'organizations': [{'title': 'Old units', 'items': [{'name': 'Old unit'}]}]}
    original = copy.deepcopy(legacy)
    with patch.object(sc, '_settings', return_value={'content': legacy}):
        loaded = sc.get_site_content(event)
    assert legacy == original and loaded['speakers'][0]['bio'] == ''
    assert loaded['organizations'][0]['items'][0]['images'] == []
    assert loaded['actions']['registration']['mode'] == 'native'
    assert [s['key'] for s in loaded['sections']][:1] == ['venue']
    assert all(not s['enabled'] for s in loaded['sections'][1:])
    sc.validate_content(event, loaded)
    content = sc.validate_content(event, {
        'introduction_images': [image], 'speakers': [{'name': 'Speaker', 'role': 'Professor', 'bio': 'Biography', 'enabled': True}],
        'dates': [{'label': 'Range', 'date': '2027-01-01', 'end_date': '2027-01-02', 'enabled': True},
                  {'date': 'Original free date', 'enabled': True}],
        'organizations': [{'title': 'Units', 'enabled': True, 'items': [{'name': 'Unit', 'description': 'Unit description', 'images': [image], 'enabled': True}]}],
        'contact': {'html': '<p>Contact <strong>team</strong></p><script>BAD()</script><a href="javascript:bad()">unsafe</a>', 'html_en': '<p>English contact</p>', 'images': [image]},
        'venue': {'description': 'Venue', 'images': [image]},
        'committees': [{'title': 'Committee fixture', 'enabled': True, 'members': [{'name': 'Member fixture', 'affiliation': 'Lab', 'enabled': True}, {'name': 'SECRET_MEMBER', 'enabled': False}]}],
        'topics': [{'title': 'Topic fixture', 'keywords': 'Keyword A\nKeyword B', 'enabled': True}], 'topic_note': 'Topic note fixture',
        'industry': [{'title': 'Industry fixture', 'goal': 'Research collaboration', 'enabled': True}, {'title': 'SECRET_INDUSTRY', 'enabled': False}],
        'showcase': ['科技成果展板', '成果路演'], 'audience': ['高校/科研院所'], 'highlights': ['精准供需对接'],
        'matchmaking': {'text': 'Matchmaking fixture', 'activities': ['专题论坛'], 'enabled': True},
        'actions': {'registration': {'enabled': True, 'mode': 'external', 'url': 'https://example.invalid/register', 'text': 'Registration notice fixture'}, 'submission': {'enabled': True, 'mode': 'external', 'url': 'mailto:papers@example.invalid', 'text': 'Submission notice fixture'}},
        'sections': [{'key': key, 'enabled': True} for key in sc.SECTIONS],
    })
    assert '<script' not in content['contact']['html'] and 'javascript:' not in content['contact']['html']
    for invalid, path in [({'organizations': [{'enabled': True, 'items': [{'enabled': True, 'description': 'x' * 301}]}]}, 'organizations[0].items[0].description'),
                          ({'organizations': [{'enabled': True, 'items': [{'enabled': True, 'url': 'https://bad.invalid/ with space'}]}]}, 'organizations[0].items[0].url'),
                          ({'introduction_images': [image] * 21}, 'introduction_images'),
                          ({'venue': {'images': ['/event/888888/attachments/foreign.png']}}, 'venue.images[0]'),
                          ({'dates': [{'date': '2027-02-02', 'end_date': '2027-01-01', 'enabled': True}]}, 'dates[0].end_date'),
                          ({'dates': [{'date': '2027-02-30', 'end_date': '2027-03-02', 'enabled': True}]}, 'dates[0].date'),
                          ({'industry': [{'title': 'Demand', 'goal': 'Email test@example.invalid', 'enabled': True}]}, 'industry[0].goal'),
                          ({'industry': [{'title': 'Demand', 'description': '电话 13800138000', 'enabled': True}]}, 'industry[0].description'),
                          ({'industry': [{'title': 'Demand', 'description': 'Visit ftp://research.example.invalid', 'enabled': True}]}, 'industry[0].description'),
                          ({'industry': [{'title': 'Demand', 'description': 'Call +1 (555) 123-4567', 'enabled': True}]}, 'industry[0].description'),
                          ({'committees': [{'enabled': True, 'members': [{'enabled': True}] * 101}]}, 'committees[0].members'),
                          ({'topics': [{'enabled': True}] * 31}, 'topics'),
                          ({'showcase': ['unknown']}, 'showcase[0]'),
                          ({'sections': [{'key': 'venue', 'enabled': True}] * 2}, 'sections')]:
        bad(invalid, path)
    bad({'theme': {'accent': 'bad color'}}, 'theme.accent')
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    assert display._date_countdown(today) == 0, 'Countdown must use Shanghai midnight without adding a day'
    assert display._date_countdown('2027-01-01 – 2027-01-02') is None
    with YujianSitePlugin.instance.plugin_context(), \
         patch.object(YujianSitePlugin.event_settings, 'get', side_effect=lambda event, key: 'academic-full' if key == 'template' else True), \
         patch.object(display.layout_settings, 'get', return_value=None), \
         patch.object(display, 'menu_entries_for_event', return_value=[]), \
         patch.object(sc, 'get_site_content', return_value=content):
        html = display.render_conference(event).get_data(as_text=True)
    assert all(text in html for text in ('Committee fixture', 'Member fixture', 'Topic fixture', 'Topic note fixture', 'Industry fixture', 'Matchmaking fixture', 'Registration notice fixture', 'Biography', 'Professor', 'Unit description'))
    assert html.count('src="' + image + '"') >= 4
    assert 'id="submission-info"' in html and 'id="registration-info"' in html
    assert html.count('Submission notice fixture') >= 1 and 'mailto:papers@example.invalid' in html
    assert all(secret not in html for secret in ('SECRET_MEMBER', 'SECRET_INDUSTRY', '<script>BAD()', 'javascript:bad()'))
    assert 'data-complete-language="zh"' in html and 'data-complete-language="en"' in html

# Verify the saved API contract and asset access using disposable fixtures only.
suffix = uuid.uuid4().hex[:12]
event_ids, user_ids = [], []
def check(response, status):
    assert response.status_code == status, (response.status_code, response.get_data(as_text=True)[:400])
    return response

try:
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        user = create_user(f'feedback-{suffix}@example.invalid', {'first_name': 'Feedback fixture', 'last_name': suffix},
                           Identity(provider='indico', identifier=f'feedback-{suffix}', password=uuid.uuid4().hex))
        user_ids.append(user.id)
        db.session.commit()
    client, anon = app.test_client(), app.test_client()
    with app.app_context():
        with client.session_transaction() as sess:
            sess.set_session_user(User.get(user_ids[0]))
        token = json.loads(check(client.get('/assets/js-vars/user.js?portal=1'), 200).data)['csrf_token']
    headers = {'X-CSRF-Token': token}
    for name in ('main', 'other'):
        result = check(client.post('/api/conferences/', headers=headers, json={
            'title': f'Feedback disposable {name} {suffix}', 'start': '2027-06-10T09:00', 'end': '2027-06-12T17:00',
            'location': 'Fixture venue', 'description': 'Native saved introduction'}), 201).json
        event_ids.append(result['id'])
    event_id, other_id = event_ids
    assert not {22, 61, 171} & set(event_ids)
    endpoint = f'/api/conferences/{event_id}/content'
    payload = check(client.get(endpoint), 200).json
    own_image = io.BytesIO()
    Image.new('RGB', (4, 3), '#ff7d4b').save(own_image, format='PNG')
    asset = check(client.post(f'/api/conferences/{event_id}/assets', headers=headers,
                             data={'file': (io.BytesIO(own_image.getvalue()), 'fixture.png')}, content_type='multipart/form-data'), 201).json['url']
    content = payload['content']
    content.update(introduction_images=[asset],
                   committees=[{'title': 'Saved committee fixture', 'enabled': True, 'members': [{'name': 'Saved member fixture', 'enabled': True}, {'name': 'SAVED_SECRET_MEMBER', 'enabled': False}]}],
                   topics=[{'title': 'Saved topic fixture', 'keywords': 'Saved keywords', 'enabled': True}],
                   industry=[{'title': 'Saved industry fixture', 'goal': 'Innovation research', 'enabled': True}],
                   showcase=['成果路演'], audience=['高校/科研院所'], highlights=['精准供需对接'],
                   matchmaking={'text': 'Saved matchmaking fixture', 'activities': ['专题论坛'], 'enabled': True})
    content['sections'] = [{'key': key, 'enabled': True} for key in sc.SECTIONS]
    content['contact'].update(html='<p>Saved contact</p><img src="javascript:bad()" onerror="bad()">', images=[asset])
    content['venue'].update(description='Saved venue', images=[asset])
    content['organizations'][0]['items'] = [{'name': 'Saved unit', 'description': 'Saved description', 'images': [asset], 'enabled': True}]
    saved = check(client.put(endpoint, json={'revision': 0, 'content': content}, headers=headers), 200).json
    assert saved['revision'] == 1 and saved['content']['committees'][0]['title'] == 'Saved committee fixture'
    assert 'javascript:' not in saved['content']['contact']['html'] and 'onerror' not in saved['content']['contact']['html']
    check(client.put(f'/api/conferences/{other_id}/content', json={'revision': 0, 'content': {'venue': {'images': [asset]}}}, headers=headers), 400)
    assert anon.get(f'/event/{event_id}/').status_code != 200 and anon.get(asset).status_code != 200
    check(client.post(f'/api/conferences/{event_id}/publication', json={'published': True}, headers=headers), 200)
    html = check(anon.get(f'/event/{event_id}/'), 200).get_data(as_text=True)
    assert all(text in html for text in ('Saved committee fixture', 'Saved member fixture', 'Saved topic fixture', 'Saved industry fixture', 'Saved matchmaking fixture', 'Saved description'))
    assert 'SAVED_SECRET_MEMBER' not in html and html.count('src="' + asset + '"') >= 4
    check(anon.get(asset), 200)
    check(client.post(f'/api/conferences/{event_id}/publication', json={'published': False}, headers=headers), 200)
    assert anon.get(asset).status_code != 200
    # Existing owners may have only the old five section rows and incomplete nested records.
    old = {'sections': [{'key': key, 'enabled': True} for key in sc.LEGACY_SECTIONS],
           'speakers': [{'name': 'Partial saved speaker'}], 'organizations': [{'title': 'Old title preserved', 'items': [{'name': 'Partial saved unit'}]}]}
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        YujianSitePlugin.event_settings.set(Event.get(other_id), 'content', old)
        db.session.commit()
    loaded = check(client.get(f'/api/conferences/{other_id}/content'), 200).json
    assert loaded['content']['organizations'][0]['title'] == 'Old title preserved'
    assert not any(row['enabled'] for row in loaded['content']['sections'] if row['key'] not in sc.LEGACY_SECTIONS)
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        assert EventSetting.query.filter_by(event_id=other_id, module='plugin_yujian_site', name='content').one().value == old
    check(client.put(f'/api/conferences/{other_id}/content', json={'revision': 0, 'content': loaded['content']}, headers=headers), 200)
finally:
    with app.test_request_context(base_url='http://192.168.2.36:12880'):
        db.session.rollback()
        for fixture_id in event_ids:
            Event.get(fixture_id).is_deleted = True
        for fixture_id in user_ids:
            User.get(fixture_id).is_deleted = True
        db.session.commit()
print('PASS feedback schema, legacy preservation, field errors, limits, own images, rich sanitization, saved public sections and private asset access')

"""Read-only rendering checks; execute in the Indico container."""
from urllib.parse import parse_qs, urlsplit
from types import SimpleNamespace
from unittest.mock import patch
from datetime import datetime

from indico.web.flask.app import make_app
from yujian_site import YujianSitePlugin
from yujian_site import display

app = make_app()
app.config['TESTING'] = True

def entry(title, children=(), visible=True, access=True, separator=False):
    return SimpleNamespace(id=title, title=title, localized_title=title, name=None,
                           children=list(children), is_visible=visible, is_separator=separator,
                           can_access=lambda user: access, url='/safe/' if not separator else None,
                           is_page=False, page_id=None, new_tab=False)

with app.test_request_context(base_url='http://192.168.2.36:12880'):
    assert hasattr(display, '_public_navigation'), 'Complete template needs recursive ACL navigation'
    tree = [entry('', separator=True), entry('visible', [entry('nested', [entry('third')]),
            entry('denied', [entry('SECRET')], access=False)]), entry('', separator=True),
            entry('', separator=True), entry('hidden', [entry('SECRET2')], visible=False),
            entry('last'), entry('', separator=True)]
    nav = display._public_navigation(tree, None)
    assert [x['title'] for x in nav] == ['visible', '', 'last']
    assert nav[0]['children'][0]['children'][0]['title'] == 'third'
    assert 'SECRET' not in repr(nav)
    from yujian_site.site_content import default_content
    event = SimpleNamespace(id=999999, title='Rendering <conference>', start_dt_local=datetime(2027, 1, 1),
                            end_dt_local=datetime(2027, 1, 2), description='<p>Intro</p><script>bad()</script>',
                            venue_name='Meet venue', timezone='Asia/Shanghai', can_manage=lambda user: False,
                            has_feature=lambda name: False, has_logo=False)
    content = default_content(event)
    content['banner']['image_en'] = '/event/999999/attachments/english-banner.png'
    content['speakers'] = [dict(name='Visible speaker', name_en='', affiliation='', affiliation_en='',
                                topic='', topic_en='', image='', enabled=True),
                           dict(name='HIDDEN_SPEAKER', enabled=False)]
    content['news'] = [dict(title='News <script>', title_en='English news', date='2027-01-01',
                           body='Plain <img onerror=bad()>', body_en='', url='', enabled=True)]
    content['organizations'][0]['items'] = [dict(name='Meet research', name_en='', image='', url='', enabled=True)]
    content['organizations'][1]['items'] = [dict(name='HIDDEN_ORG', enabled=False)]
    native_submission = entry('NATIVE_ABSTRACTS')
    native_submission.name = 'call_for_abstracts'
    native_submission.url = '/event/999999/abstracts/'
    tree.append(native_submission)
    content['actions']['submission'].update(enabled=True, mode='external', url='mailto:conference@example.invalid')
    def settings(event, key):
        return {'template': 'academic-full', 'published': True}.get(key)
    with YujianSitePlugin.instance.plugin_context(), \
         patch.object(YujianSitePlugin.event_settings, 'get', side_effect=settings), \
         patch.object(display.layout_settings, 'get', return_value=None), \
         patch.object(display, 'menu_entries_for_event', return_value=tree), \
         patch('yujian_site.site_content.get_site_content', return_value=content):
        response = display.render_conference(event)
    html = response.get_data(as_text=True)
    assert 'complete-conference.css' in html and 'complete-conference.js' in html
    assert 'data-conference-entry' in html, 'Conference pages need prominent enrollment and login buttons'
    assert 'conference-entry.css' in html and 'data-conference-login' in html
    assert 'aria-disabled="true"' in html and 'data-conference-enroll' not in html
    assert '<header class="complete-banner has-image">' in html
    assert 'src="/event/999999/attachments/english-banner.png"' in html
    assert 'data-image-zh="/event/999999/attachments/english-banner.png"' in html
    assert 'data-image-en="/event/999999/attachments/english-banner.png"' in html
    assert 'Visible speaker' in html and 'Meet research' in html and 'English news' in html
    assert all(secret not in html for secret in ('HIDDEN_SPEAKER', 'HIDDEN_ORG', 'SECRET', '<script>bad()'))
    assert 'News &lt;script&gt;' in html and 'Plain &lt;img onerror=bad()&gt;' in html
    assert 'data-en="Visible speaker"' in html, 'Empty English must fall back to Chinese'
    assert 'href="/event/999999/registrations/"' not in html
    assert 'NATIVE_ABSTRACTS' not in html and 'href="/event/999999/abstracts/"' not in html
    assert 'href="mailto:conference@example.invalid"' in html
    assert response.headers['Cache-Control'] == 'private, no-store'
    content['actions']['registration']['enabled'] = True
    content['actions']['submission'].update(enabled=True, mode='native', url='')
    event.has_feature = lambda name: True
    event.registration_forms = [SimpleNamespace(private=True, is_active=True),
                                SimpleNamespace(private=False, is_active=False)]
    event.cfa = SimpleNamespace(is_open=False)
    actions = display._complete_actions(event, content)
    assert actions[0]['url'] == '' and actions[0]['state_en'] == 'Registration is not open'
    assert urlsplit(actions[1]['url']).path == '/login/' and parse_qs(urlsplit(actions[1]['url']).query)['next'] == ['/event/999999/abstracts/']
    assert actions[1]['state_en'] == 'Submissions are closed'
    event.registration_forms.append(SimpleNamespace(private=False, is_active=True))
    assert parse_qs(urlsplit(display._complete_actions(event, content)[0]['url']).query)['next'] == ['/event/999999/registrations/']
    enroll = display._conference_entry(event, display._complete_actions(event, content))
    assert enroll['member_url'] == '/event/999999/registrations/'
    assert parse_qs(urlsplit(enroll['guest_url']).query)['next'] == ['/event/999999/registrations/']
    assert display._conference_entry(event, [])['member_url'] == '', 'Respect explicitly disabled enrollment'
    content['actions']['registration'].update(mode='external', url='https://conference.example.com/register')
    external = display._conference_entry(event, display._complete_actions(event, content))
    assert external['guest_url'] == external['member_url'] == 'https://conference.example.com/register'
    content['actions']['submission'].update(mode='external', url='mailto:conference@example.invalid')
    assert display._complete_actions(event, content)[1]['url'].startswith('mailto:')
    for url in ('javascript:alert(1)', '//evil.invalid', '/\\evil.invalid', '/safe/\nunsafe', 'https://[broken'):
        assert not display._safe_public_url(url)
    for legacy in ('academic', 'industry'):
        with patch.object(YujianSitePlugin.event_settings, 'get', side_effect=lambda event, key: legacy if key == 'template' else True), \
             patch.object(display.layout_settings, 'get', return_value=None), \
             patch.object(display, 'menu_entries_for_event', return_value=[]), \
             patch.object(display, 'render_plugin_template', return_value='legacy') as render:
            assert display.render_conference(event).get_data(as_text=True) == 'legacy'
            assert render.call_args.args[0] == 'conference-site.html'
print('PASS recursive ACL, separators, enabled filtering, escaping, fallback, disabled actions and cache headers')

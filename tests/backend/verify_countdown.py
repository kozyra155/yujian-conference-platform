"""Countdown schema and render contract; no persistent writes or outgoing mail."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from werkzeug.exceptions import BadRequest
from indico.web.flask.app import make_app
from yujian_site import YujianSitePlugin, display, site_content as sc

app = make_app(config_override={'EMAIL_BACKEND': 'indico.vendor.django_mail.backends.locmem.EmailBackend', 'SMTP_USE_CELERY': False})
app.config['TESTING'] = True
event = SimpleNamespace(id=999999, title='Countdown fixture', start_dt=datetime(2027, 10, 19, 18, tzinfo=timezone.utc),
    start_dt_local=datetime(2027, 10, 19, 14), end_dt_local=datetime(2027, 10, 21), timezone='America/New_York',
    description='', venue_name='', can_manage=lambda user: False, has_feature=lambda name: False, has_logo=False)
with app.test_request_context(base_url='http://192.168.2.36:12880'):
    assert sc.default_content(event)['countdown'] == {'enabled': False, 'target_date': ''}
    with patch.object(sc, '_settings', return_value={'content': {'banner': {'title': 'Legacy'}}}):
        assert sc.get_site_content(event)['countdown']['enabled'] is False
    content = sc.validate_content(event, {'countdown': {'enabled': True, 'target_date': ''}})
    clock = display._conference_countdown(event, content['countdown'])
    assert clock['target'] == '2027-10-20T00:00:00+08:00', clock
    assert clock['is_conference'] is True
    class FixedNow(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2027, 9, 7, 9, 41, 45, tzinfo=timezone.utc).astimezone(tz)
    with patch.object(display, 'datetime', FixedNow):
        clock = display._conference_countdown(event, content['countdown'])
        assert [clock[key] for key in ('days', 'hours', 'minutes', 'seconds')] == [42, 6, 18, 15]
    event.start_dt = datetime(2027, 10, 20, 18, tzinfo=timezone.utc)
    assert display._conference_countdown(event, content['countdown'])['target'] == '2027-10-21T00:00:00+08:00'
    event.start_dt = datetime(2027, 10, 19, 18, tzinfo=timezone.utc)
    assert display._conference_countdown(event, {'enabled': False}) is None
    for value in ('2027-02-30', '2027-1-01', '20271020', '2027-10-20T09:00', 'bad'):
        try:
            sc.validate_content(event, {'countdown': {'enabled': True, 'target_date': value}})
        except BadRequest as error:
            assert 'countdown.target_date' in error.description
        else:
            raise AssertionError(f'Invalid countdown date accepted: {value}')
    custom = sc.validate_content(event, {'countdown': {'enabled': True, 'target_date': '2027-11-02'}})
    clock = display._conference_countdown(event, custom['countdown'])
    assert clock['target'] == '2027-11-02T00:00:00+08:00' and not clock['is_conference']
    expired = display._conference_countdown(event, {'enabled': True, 'target_date': '2000-01-01'})
    assert expired['expired'] and all(expired[key] == 0 for key in ('days', 'hours', 'minutes', 'seconds'))
    with YujianSitePlugin.instance.plugin_context(), \
         patch.object(YujianSitePlugin.event_settings, 'get', side_effect=lambda event, key: 'academic-full' if key == 'template' else True), \
         patch.object(display.layout_settings, 'get', return_value=None), \
         patch.object(display, 'menu_entries_for_event', return_value=[]), \
         patch.object(sc, 'get_site_content', return_value=content):
        html = display.render_conference(event).get_data(as_text=True)
        assert 'data-live-countdown' in html and '2027-10-20T00:00:00+08:00' in html
        assert 'role="timer"' in html and 'aria-live="off"' in html
        page = SimpleNamespace(id=1, menu_entry=SimpleNamespace(title='Page fixture'), html='Page body')
        html = display._render_complete_conference(event, page, YujianSitePlugin.instance).get_data(as_text=True)
        assert 'data-live-countdown' not in html, 'Countdown appears on the homepage only'
        content['countdown']['enabled'] = False
        html = display.render_conference(event).get_data(as_text=True)
        assert 'data-live-countdown' not in html
print('PASS: countdown defaults, legacy read, date validation, Shanghai midnight, custom target, expiry, render and disabled state')

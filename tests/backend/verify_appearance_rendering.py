"""Read-only assertions for actual appearance rendering and preview isolation."""
import copy
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from indico.web.flask.app import make_app
from yujian_site import YujianSitePlugin, display
from yujian_site.site_content import default_content

app = make_app()
app.config['TESTING'] = True
with app.test_request_context(base_url='http://192.168.2.36:12880'):
    event = SimpleNamespace(id=999999, title='Appearance fixture', start_dt_local=datetime(2027, 1, 1),
                            end_dt_local=datetime(2027, 1, 2), description='<p>UNCHANGED-INTRO</p>',
                            venue_name='Example venue', timezone='Asia/Shanghai', can_manage=lambda user: False,
                            has_feature=lambda name: False, has_logo=False)
    content = default_content(event)
    before = copy.deepcopy(content)
    with YujianSitePlugin.instance.plugin_context(), \
         patch.object(YujianSitePlugin.event_settings, 'get', side_effect=lambda event, key: 'academic' if key == 'template' else True), \
         patch.object(display.layout_settings, 'get', return_value=None), \
         patch.object(display, 'menu_entries_for_event', return_value=[]), \
         patch('yujian_site.site_content.get_site_content', return_value=content):
        for layout in ('simple-1', 'simple-2'):
            for accent in ('#fa7d4b', '#d94a45', '#8550ad', '#3f67c8', '#293d78', '#488b35'):
                response = display.render_conference(event, theme_override={'layout': layout, 'accent': accent})
                html = response.get_data(as_text=True)
                assert f'appearance-{layout}' in html
                assert f'--complete-accent:{accent}' in html
                assert 'appearance-presets.css' in html and 'UNCHANGED-INTRO' in html
                assert response.headers['Cache-Control'] == 'private, no-store'
    assert content == before, 'Preview must not mutate even in-memory source content'
print('PASS twelve actual rendered appearances, forced preview of legacy template, no mutation')

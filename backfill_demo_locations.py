"""Adopt the two original demos without resetting content, appearance or permissions."""
from indico.web.flask.app import make_app
from indico.core.db import db
from indico.modules.events import Event
from indico.modules.events.util import track_location_changes
from yujian_site import YujianSitePlugin

app = make_app()
with app.test_request_context(base_url='http://localhost:12880'), track_location_changes():
    count = 0
    adopted = 0
    for slug, city in [('yujian-ai2027', '上海'), ('yujian-energy2027', '长沙')]:
        event = Event.query.filter_by(url_shortcut=slug, is_deleted=False).one_or_none()
        if event and not event.venue_name:
            event.inherit_location = False
            event.venue_name = city
            count += 1
        if event and not YujianSitePlugin.event_settings.get(event, 'managed'):
            YujianSitePlugin.event_settings.set_multi(event, {'managed': True,
                'published': event.can_access(None) and event.visibility != 0})
            adopted += 1
    db.session.commit()
    print(f'Filled {count} missing locations; adopted {adopted} demonstration sites. Existing content was preserved.')

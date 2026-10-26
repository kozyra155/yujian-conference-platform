"""Validate the isolated demo using Indico's real models and permission rules."""
import json

from flask import session
import indico
from indico.core.config import config
from indico.web.flask.app import make_app
from indico.modules.auth import Identity
from indico.modules.events import Event
from indico.modules.events.layout import layout_settings
from indico.modules.events.layout.models.menu import MenuEntry, MenuEntryType

app = make_app()
with app.test_request_context(base_url='http://192.168.2.36:12880'):
    assert indico.__version__ == '3.3.13'
    demo_email = config.EMAIL_BACKEND == 'indico.vendor.django_mail.backends.locmem.EmailBackend'
    assert demo_email or config.EMAIL_BACKEND == 'indico.vendor.django_mail.backends.smtp.EmailBackend'
    if not demo_email:
        assert config.SMTP_USE_SSL != config.SMTP_USE_TLS
        assert config.NO_REPLY_EMAIL == config.SMTP_LOGIN
    assert config.CELERY_CONFIG['worker_concurrency'] == 1
    events = [Event.query.filter_by(url_shortcut=slug).one_or_none()
              for slug in ('yujian-ai2027', 'yujian-energy2027')]
    assert all(events), 'Two demo conferences have not been created yet'
    users = [Identity.query.filter_by(provider='indico', identifier=name).one().user
             for name in ('host-a', 'host-b')]
    checks = []
    for index, (event, owner) in enumerate(zip(events, users)):
        other = users[1 - index]
        assert not owner.is_admin, 'Host must not have global admin privileges'
        assert event.category.can_create_events(owner), 'Demo host cannot create a conference in the demo category'
        assert not event.category.can_manage(owner), 'Creation permission must not grant category administration'
        assert not event.category.can_create_events(None), 'Anonymous conference creation must be denied'
        assert event.can_manage(owner), 'Owner cannot manage their own conference'
        assert not event.can_manage(other), 'Cross-conference management access leaked'
        assert event.can_access(None), 'Public conference must be visible anonymously'
        assert not event.can_manage(None), 'Anonymous visitor has management access'
        entries = MenuEntry.query.filter_by(event_id=event.id, type=MenuEntryType.page).all()
        assert len(entries) >= 6, 'Default conference pages are missing'
        assert all(entry.page.event_id == event.id for entry in entries)
        assert layout_settings.get(event, 'use_custom_menu')
        session.set_session_user(owner)
        checks.append({'event_id': event.id, 'title': event.title,
                       'url': f'http://192.168.2.36:12880/event/{event.id}/',
                       'pages': len(entries), 'owner_access': True,
                       'other_host_denied': True, 'anonymous_manage_denied': True})
    assert events[0].id != events[1].id
    assert events[0].description != events[1].description
    assert (layout_settings.get(events[0], 'header_background_color') !=
            layout_settings.get(events[1], 'header_background_color'))
    print(json.dumps({'passed': True, 'version': indico.__version__,
                      'external_email_disabled': demo_email, 'events': checks}, ensure_ascii=False, indent=2))

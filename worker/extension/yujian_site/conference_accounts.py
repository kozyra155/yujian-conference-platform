"""Conference context for the existing native login and email-verified signup."""
import re
from urllib.parse import unquote, urlsplit, urlunsplit

from flask import g, request, session
from werkzeug.exceptions import Forbidden, NotFound

from indico.core.config import config
from indico.modules.events import Event
from indico.web.flask.util import url_for

from . import YujianSitePlugin


def safe_conference_target(value, event_id=None):
    if not isinstance(value, str) or '\\' in value or any(ord(c) < 33 for c in value):
        return None
    try:
        parsed = urlsplit(value)
        origin = urlsplit(config.BASE_URL)
    except ValueError:
        return None
    if parsed.netloc or parsed.scheme:
        if (parsed.scheme != origin.scheme or parsed.netloc.lower() != origin.netloc.lower()):
            return None
    if parsed.path != unquote(parsed.path):
        return None
    match = re.fullmatch(r'/event/([1-9]\d*)/(?:(?:registrations|abstracts|page|overview|interest)(?:/[A-Za-z0-9_-]+)*/?)?',
                         parsed.path)
    if not match or len(match[1]) > 10 or int(match[1]) > 2**31 - 1:
        return None
    if event_id is not None and int(match[1]) != event_id:
        return None
    return urlunsplit(('', '', parsed.path, parsed.query, parsed.fragment))


def accessible_conference(event_id):
    if not 1 <= event_id <= 2**31 - 1:
        raise NotFound()
    event = Event.get(event_id)
    if not event or event.is_deleted or not YujianSitePlugin.event_settings.get(event, 'managed'):
        raise NotFound()
    if (not event.can_access(session.user) or
            (YujianSitePlugin.instance.is_draft(event) and not event.can_manage(session.user))):
        raise Forbidden()
    return event


def account_links(event, target=None):
    target = target or f'/event/{event.id}/'
    return {'event_id': event.id, 'title': event.title, 'event_url': f'/event/{event.id}/', 'next': target,
            'login_url': url_for('auth.login', next=target),
            'register_url': url_for('auth.register', next=target)}


def prepare_native_auth(rh):
    if getattr(rh, 'provider_name', None) is not None:
        return
    registering = type(rh).__name__ == 'RHRegister'
    value = request.args.get('next') if 'next' in request.args else (
        session.get('register_next_url') if registering else None)
    target = safe_conference_target(value)
    if target:
        try:
            event = accessible_conference(int(target.split('/')[2]))
        except (Forbidden, NotFound):
            target = None
        else:
            g.conference_auth = account_links(event, target)
    if registering:
        from .registration_progress import prepare_registration
        prepare_registration(rh, target)

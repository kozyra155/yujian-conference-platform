"""Website creation and publication use native transactions, sessions and ACLs."""
from flask import jsonify, redirect, request, session
from flask_pluginengine import render_plugin_template
from markupsafe import escape
from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import JSONB
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound, Unauthorized

from indico.core.db import db
from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.core.plugins import IndicoPluginBlueprint
from indico.modules.categories import Category
from indico.modules.events import Event
from indico.modules.events.models.events import EventType
from indico.modules.events.models.settings import EventSetting
from indico.modules.events.operations import create_event
from indico.modules.events.util import check_event_locked
from indico.modules.events.layout import layout_settings
from indico.web.rh import RH, RHProtected
from indico.util.string import html_to_plaintext
from . import YujianSitePlugin
from .appearances import validate_theme
from .conference_metadata import conference_phase, get_metadata, location_name, parse_dates, validate_metadata
from .conference_search import filter_conferences
from .site_content import TEMPLATES, ensure_complete_site, get_content_payload, upload_image, validate_content

bp = IndicoPluginBlueprint('yujian_site', __name__)


@bp.after_request
def private_api_response(result):
    if request.path.startswith('/api/'):
        result.headers['Cache-Control'] = 'private, no-store'
    return result


def response(data, status=200):
    result = jsonify(data)
    result.status_code = status
    result.headers['Cache-Control'] = 'private, no-store'
    return result


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise BadRequest('Expected a JSON object.')
    return data


def text(data, key, limit, required=True):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value.strip()) > limit or (required and not value.strip()):
        raise BadRequest(f'{key}: required text, maximum {limit} characters.')
    return value.strip()


def serialize(event, private=False):
    settings = YujianSitePlugin.event_settings
    result = {'id': event.id, 'title': event.title, 'url': f'/event/{event.id}/',
              'start': event.start_dt.isoformat(), 'end': event.end_dt.isoformat(),
              'location': event.venue_name, 'timezone': event.timezone,
              'description': html_to_plaintext(str(event.description) or '<p></p>')[:300],
              'phase': conference_phase(event), **get_metadata(event)}
    if private:
        result.update(published=settings.get(event, 'published'), builder_url=f'/conference/{event.id}/')
    return result


class RHAccount(RHProtected):
    def _check_access(self):
        if not session.user and request.path.startswith('/api/'):
            raise Unauthorized()
        super()._check_access()
        user = session.user
        if user.is_deleted or user.is_blocked or user.is_pending:
            raise Forbidden('An active, verified account is required.')


class RHCreatePage(RHAccount):
    def _process(self):
        return render_plugin_template('builder.html', mode='create', event=None)


class RHConferenceAccount(RH):
    def _process(self):
        from .conference_accounts import accessible_conference, account_links, safe_conference_target
        event = accessible_conference(request.view_args['event_id'])
        target = safe_conference_target(request.args.get('next', f'/event/{event.id}/'), event.id)
        if not target:
            raise BadRequest('The return address must be a public page of this conference.')
        links = account_links(event, target)
        return redirect(links['register_url' if request.endpoint.endswith('conference_register') else 'login_url'])


class RHOrganizer(RHAccount):
    def _process(self):
        return render_plugin_template('builder.html', mode='organizer', event=None)


class RHManaged(RHAccount):
    def _process_args(self):
        self.event = Event.get(request.view_args['event_id'])
        if not self.event or self.event.is_deleted or not YujianSitePlugin.event_settings.get(self.event, 'managed'):
            raise NotFound()

    def _check_access(self):
        super()._check_access()
        if not self.event.can_manage(session.user):
            raise Forbidden()
        check_event_locked(self, self.event)


class RHWebsite(RHManaged):
    def _process(self):
        return render_plugin_template('builder.html', mode='website', event=self.event,
                                      published=YujianSitePlugin.event_settings.get(self.event, 'published'))


class RHOperationsPage(RHManaged):
    def _process(self):
        return render_plugin_template('builder.html', mode='operations', event=self.event)


class RHParticipationPage(RHAccount):
    def _process(self):
        return render_plugin_template('builder.html', mode='participation', event=None)


class RHOperations(RHManaged):
    def _process(self):
        from .business import operations
        return response(operations(self.event))


class RHParticipation(RHAccount):
    def _process(self):
        from .business import participation
        return response(participation(session.user))


class RHCreate(RHAccount):
    def _process(self):
        data = body()
        title = text(data, 'title', 200)
        metadata = validate_metadata(data)
        location = location_name(metadata) or text(data, 'location', 200)
        description = text(data, 'description', 10000)
        template = data.get('template', 'academic-full')
        if template not in TEMPLATES:
            raise BadRequest('Unknown website template.')
        dates = parse_dates(data)
        category = Category.get(YujianSitePlugin.settings.get('category_id'))
        if not category or category.is_deleted or not category.can_access(None):
            raise BadRequest('The platform conference category is unavailable.')
        # Grant only category creation, never category management or global administration.
        category.update_principal(session.user, add_permissions={'create'})
        event = create_event(category, EventType.conference, {
            'title': title, 'description': f'<p>{escape(description)}</p>'.replace('\n', '<br>'),
            'start_dt': dates[0], 'end_dt': dates[1], 'timezone': 'Asia/Shanghai',
            'location_data': {'inheriting': False, 'venue_name': location, 'room_name': '',
                              'address': metadata['detail_address']}})
        event.organizer_info = str(escape(metadata['organizer_name']))
        event.contact_phones = [metadata['organizer_phone']] if metadata['organizer_phone'] else []
        YujianSitePlugin.event_settings.set_multi(event, {'template': template, 'conference_metadata': metadata})
        if template == 'academic-full':
            ensure_complete_site(event, new=True)
        if template == 'industry':
            layout_settings.set(event, 'header_background_color', '#287a67')
        return response(serialize(event, private=True), 201)


class RHPublication(RHManaged):
    def _process(self):
        value = body().get('published')
        if type(value) is not bool:
            raise BadRequest('published must be a boolean.')
        if value and not self.event.category.can_access(None):
            raise BadRequest('This category is not public.')
        self.event.protection_mode = ProtectionMode.public if value else ProtectionMode.protected
        self.event.visibility = None if value else 0
        self.event.access_key = ''
        YujianSitePlugin.event_settings.set(self.event, 'published', value)
        return response(serialize(self.event, private=True))


class RHContent(RHManaged):
    def _process(self):
        if request.method == 'GET':
            return response(get_content_payload(self.event))
        data = body()
        if set(data) - {'revision', 'content', 'template'} or type(data.get('revision')) is not int:
            raise BadRequest('Expected revision, content, and optional template.')
        # Lock the event even when this is the first content save and no setting row exists yet.
        self.event = Event.query.filter_by(id=self.event.id).populate_existing().with_for_update().one()
        self._check_access()
        current = get_content_payload(self.event)
        if data['revision'] != current['revision']:
            raise Conflict('This website was updated by another manager. Refresh before saving.')
        template = data.get('template', current['template'])
        if template not in TEMPLATES:
            raise BadRequest('Unknown website template.')
        content = validate_content(self.event, data.get('content'))
        from .interests import sync_interest_forms
        sync_interest_forms(self.event, content)
        YujianSitePlugin.event_settings.set_multi(self.event, {
            'content': content, 'content_revision': current['revision'] + 1, 'template': template})
        if template == 'academic-full':
            ensure_complete_site(self.event)
        return response(get_content_payload(self.event))


class RHAppearancePreview(RHManaged):
    def _process(self):
        from .display import render_conference
        data = body()
        if set(data) != {'theme'}:
            raise BadRequest('Expected only the theme field.')
        return render_conference(self.event, theme_override=validate_theme(data['theme']))


class RHAssets(RHManaged):
    def _process(self):
        upload = request.files.get('file')
        if upload is None:
            raise BadRequest('Expected a multipart image in the file field.')
        # Serialize folder creation alongside content saves without committing the transaction early.
        self.event = Event.query.filter_by(id=self.event.id).populate_existing().with_for_update().one()
        self._check_access()
        return response({'url': upload_image(self.event, upload)}, 201)


class RHMyEvents(RHAccount):
    def _process(self):
        query = Event.query.filter_by(is_deleted=False)
        managed = EventSetting.query.filter_by(module='plugin_yujian_site', name='managed').filter(
            EventSetting.event_id == Event.id, EventSetting.value == db.literal(True, type_=JSONB)).exists()
        # Use native full-management ACLs, including delegated and inherited access.
        # shortcut: scans platform websites; add ACL-aware pagination for large installations.
        events = [event for event in query.filter(managed).options(
            db.selectinload(Event.acl_entries), db.selectinload(Event.category).selectinload(Category.acl_entries)
        ).order_by(Event.id.desc()) if event.can_manage(session.user)]
        return response({'events': [serialize(e, private=True) for e in events]})


class RHPublicEvents(RH):
    def _process(self):
        try:
            page = int(request.args.get('page', '1'))
            if not 1 <= page <= 2**31 - 1:
                raise ValueError()
        except ValueError:
            raise BadRequest('Invalid page number.') from None
        private_draft = EventSetting.query.filter_by(module='plugin_yujian_site', name='published').filter(
            EventSetting.event_id == Event.id, EventSetting.value == db.literal(False, type_=JSONB)).exists()
        hidden = EventSetting.query.filter_by(module='layout', name='is_searchable').filter(
            EventSetting.event_id == Event.id, EventSetting.value == db.literal(False, type_=JSONB)).exists()
        query = Event.query.filter(Event.category_id == YujianSitePlugin.settings.get('category_id'),
                                   ~Event.is_deleted, Event._type == EventType.conference,
                                   Event.effective_protection_mode == ProtectionMode.public,
                                   or_(Event.visibility.is_(None), Event.visibility != 0), ~private_draft, ~hidden)
        query, facets = filter_conferences(query, request.args)
        keyword = request.args.get('q', '').strip()[:200]
        if keyword:
            pattern = '%' + keyword.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
            query = query.filter(or_(Event.title.ilike(pattern, escape='\\'),
                                     Event.own_venue_name.ilike(pattern, escape='\\')))
        count = query.count()
        events = query.order_by(Event.id.desc()).offset((page - 1) * 12).limit(12).all()
        result = {'events': [serialize(e) for e in events], 'total': count, 'page': page,
                  'has_more': page * 12 < count}
        if facets is not None:
            result['filters'] = facets
        return response(result)


bp.add_url_rule('/conference/create/', 'create_page', RHCreatePage)
bp.add_url_rule('/event/<int:event_id>/login/', 'conference_login', RHConferenceAccount)
bp.add_url_rule('/event/<int:event_id>/register/', 'conference_register', RHConferenceAccount)
bp.add_url_rule('/organizer/', 'organizer', RHOrganizer)
bp.add_url_rule('/conference/<int:event_id>/', 'website', RHWebsite)
bp.add_url_rule('/conference/<int:event_id>/operations/', 'operations_page', RHOperationsPage)
bp.add_url_rule('/participation/', 'participation_page', RHParticipationPage)
bp.add_url_rule('/api/conferences/<int:event_id>/operations', 'operations', RHOperations, methods=['GET'])
bp.add_url_rule('/api/participation/', 'participation', RHParticipation, methods=['GET'])
bp.add_url_rule('/api/conferences/', 'public', RHPublicEvents, methods=['GET'])
bp.add_url_rule('/api/conferences/', 'create', RHCreate, methods=['POST'])
bp.add_url_rule('/api/conferences/<int:event_id>/publication', 'publication', RHPublication, methods=['POST'])
bp.add_url_rule('/api/conferences/<int:event_id>/content', 'content', RHContent, methods=['GET', 'PUT'])
bp.add_url_rule('/api/conferences/<int:event_id>/appearance-preview', 'appearance_preview', RHAppearancePreview,
                methods=['POST'])
bp.add_url_rule('/api/conferences/<int:event_id>/assets', 'assets', RHAssets, methods=['POST'])
bp.add_url_rule('/api/organizer/conferences/', 'mine', RHMyEvents)

from .payment_routes import register_routes
register_routes(bp)

from .conference_metadata import register_routes as register_metadata_routes
register_metadata_routes(bp)

from .interests import register_routes as register_interest_routes
register_interest_routes(bp)

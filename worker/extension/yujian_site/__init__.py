"""Indico extension for self-service conference websites."""
from flask import g, redirect, request, session
from werkzeug.exceptions import Forbidden

from indico.core import signals
from indico.core.db import db
from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.core.plugins import IndicoPlugin
from indico.modules.events.models.events import EventType
from indico.modules.events import Event
from indico.modules.attachments.models.attachments import Attachment
from indico.modules.attachments.models.folders import AttachmentFolder
from indico.modules.events.layout import layout_settings
from indico.modules.events.layout.models.menu import EventPage, MenuEntry, MenuEntryType
from indico.util.string import html_to_plaintext
from markupsafe import escape


class YujianSitePlugin(IndicoPlugin):
    """遇见科技一键建站

    Self-service creation, private drafts, publication and conference listings.
    """
    default_settings = {'category_id': 1, 'company_payments': None}
    default_event_settings = {'managed': False, 'published': False, 'template': 'academic',
                              'content': None, 'content_revision': 0, 'company_collection': False,
                              'conference_metadata': None, 'basic_revision': 0, 'interest_forms': {}}

    def init(self):
        super().init()
        self.connect(signals.event.created, self.initialize)
        self.connect(signals.rh.before_process, self.redirect_native_creation)
        self.connect(signals.acl.can_access, self.draft_access, sender=Event)
        self.connect(signals.acl.can_access, self.draft_access, sender=Attachment)
        self.connect(signals.acl.can_access, self.draft_access, sender=AttachmentFolder)
        self.connect(signals.menu.items, self.management_link, sender='event-management-sidemenu')
        from .payments import on_registration, protect_registration, protect_form, protect_event
        self.connect(signals.event.registration_created, on_registration)
        self.connect(signals.event.registration_state_updated, on_registration)
        self.connect(signals.event.registration_deleted, protect_registration)
        self.connect(signals.event.registration_form_deleted, protect_form)
        self.connect(signals.event.registration_form_edited, protect_form)
        self.connect(signals.event.deleted, protect_event)
        from .payments import protect_native_financial_changes
        self.connect(signals.rh.before_process, protect_native_financial_changes)
        from .interests import suppress_interest_notifications, protect_interest_submission
        self.connect(signals.rh.before_process, protect_interest_submission)
        self.connect(signals.plugin.interceptable_function, suppress_interest_notifications,
                     sender='indico.modules.events.registration.notifications._notify_registration')
        self.template_hook('html-head', self.website_styles)
        from .legacy import configure_exports
        configure_exports()

    def get_blueprints(self):
        from .blueprint import bp
        return bp

    def initialize(self, event, cloning=False, **kwargs):
        if (cloning or event.type_ != EventType.conference or
                event.category_id != self.settings.get('category_id') or self.event_settings.get(event, 'managed')):
            return
        self.event_settings.set_multi(event, {'managed': True, 'published': False})
        event.protection_mode = ProtectionMode.protected
        event.visibility = 0
        layout_settings.set_multi(event, {'use_custom_menu': True, 'header_background_color': '#245a76',
                                         'header_text_color': '#ffffff', 'show_social_badges': False})
        # Build in the creation transaction; the native menu helper uses a separate transaction.
        db.session.add(MenuEntry(event=event, type=MenuEntryType.internal_link,
                                 name='overview', title='会议首页', position=0, is_enabled=True))
        content = [('会议委员会', '请填写大会主席、委员会成员及所属单位。'),
                   ('会议主题', html_to_plaintext(str(event.description) or '<p></p>')),
                   ('会议日程', f'{event.start_dt_local:%Y-%m-%d} 至 {event.end_dt_local:%Y-%m-%d}。请补充详细议程。'),
                   ('会议地点', event.venue_name or '请填写会议地点与交通信息。'),
                   ('重要通知', '请在这里发布会议通知、重要日期与参会须知。'),
                   ('联系我们', '请填写主办方名称及对外联系方式。')]
        for position, (title, text) in enumerate(content, 1):
            page = EventPage(event=event, html=f'<h2>{escape(title)}</h2><p>{escape(text)}</p>')
            db.session.add(MenuEntry(event=event, type=MenuEntryType.page, title=title,
                                     page=page, position=position, is_enabled=True))

    def redirect_native_creation(self, sender, rh, **kwargs):
        if sender.__name__ in {'RHLogin', 'RHRegister'}:
            from .conference_accounts import prepare_native_auth
            prepare_native_auth(rh)
        if sender.__name__ == 'RHCreateEvent' and not request.is_xhr and rh.event_type == EventType.conference:
            return redirect('/conference/create/')
        event = getattr(rh, 'event', None)
        if event and self.event_settings.get(event, 'company_collection', False):
            if sender.__name__ == 'RHRegistrationTogglePayment':
                raise Forbidden('请在公司收款工作台核对到账或退款 / Use company finance to record payments or refunds.')
            if sender.__name__ == 'RHPaymentCheckout' and getattr(rh, 'registration', None):
                return redirect(f'/payments/{rh.registration.id}/')
        if self.is_draft(event) and not event.can_manage(session.user):
            raise Forbidden('This conference website is a private draft.')
        # Set before native body rendering; html-head hooks run after the body is rendered.
        if (event and event.type_ == EventType.conference and self.event_settings.get(event, 'managed')
                and not request.is_xhr):
            prefix = f'/event/{event.id}/'
            path = request.path.removeprefix(prefix)
            if request.path.startswith(prefix) and path.startswith(
                    ('manage/registration/', 'manage/abstracts/', 'registrations/', 'abstracts/')):
                management = path.startswith('manage/')
                registration = path.startswith(('manage/registration/', 'registrations/'))
                from indico.modules.events.registration import REGISTRATION_PERMISSIONS
                g.yujian_native_business = {
                    'management': management, 'registration': registration,
                    'can_manage_registration': any(event.can_manage(session.user, permission=p) for p in REGISTRATION_PERMISSIONS),
                    'can_manage_abstracts': event.can_manage(session.user, permission='abstracts'),
                    'title_zh': ('报名管理' if registration else '投稿与审稿管理') if management else
                                ('会议报名' if registration else '投稿与审稿'),
                    'title_en': ('Registration management' if registration else 'Abstract management') if management else
                                ('Conference registration' if registration else 'Abstracts and reviewing'),
                    'event_url': str(event.url), 'event_id': event.id,
                }
        # This hook runs after native URL normalization and access checks.
        from .display import render_conference, render_workspace, render_menu_editor
        if (sender.__name__ == 'RHDisplayCategory' and
                rh.category.id == self.settings.get('category_id') and not request.args.get('legacy')):
            return render_workspace('directory')
        if (sender.__name__ == 'RHUserDashboard' and rh.user == session.user and
                not request.args.get('legacy')):
            return render_workspace('organizer')
        if event and self.event_settings.get(event, 'managed'):
            if sender.__name__ == 'RHMenuEdit':
                return render_menu_editor(event)
            if layout_settings.get(event, 'use_custom_css') or layout_settings.get(event, 'theme'):
                return  # Explicit native themes keep their own markup, CSS and preview behavior.
            if sender.__name__ == 'RHDisplayEvent' and not rh.theme_override:
                page = None
                if not rh.force_overview and event.default_page and event.default_page.menu_entry.can_access(session.user):
                    page = event.default_page
                return render_conference(event, page)
            if sender.__name__ == 'RHPageDisplay':
                return render_conference(event, rh.page)

    def is_draft(self, event):
        return (event is not None and event.id is not None and self.event_settings.get(event, 'managed') and
                not self.event_settings.get(event, 'published'))

    def draft_access(self, sender, obj, user, allow_admin, **kwargs):
        if obj.id is None:
            return
        event = obj if isinstance(obj, Event) else obj.folder.event if isinstance(obj, Attachment) else obj.event
        if self.is_draft(event) and not event.can_manage(user, allow_admin=allow_admin):
            return False

    def website_styles(self):
        rh = getattr(g, 'rh', None)
        event = getattr(rh, 'event', None)
        editor = (rh and type(rh).__name__ == 'RHMenuEdit' and event and
                  self.event_settings.get(event, 'managed'))
        user_page = request.path.startswith('/user/') and getattr(rh, 'user', None) == session.user and session.user
        native_business = getattr(g, 'yujian_native_business', None)
        if editor or user_page or native_business:
            assets = ('<meta name="viewport" content="width=device-width, initial-scale=1">'
                      '<link rel="stylesheet" href="/portal-assets/portal.css">'
                      '<link rel="stylesheet" href="/portal-assets/ui-dist/workspace.css">'
                      '<link rel="stylesheet" href="/portal-assets/native-frame.css">'
                      '<script src="/portal-assets/translations.js" defer></script>'
                      '<script src="/portal-assets/portal.js" defer></script>'
                      '<script src="/portal-assets/native-frame.js" defer></script>')
            if editor:
                assets += ('<link rel="stylesheet" href="/portal-assets/menu-editor.css">'
                           '<script src="/portal-assets/menu-editor.js" defer></script>'
                           '<script type="module" src="/portal-assets/ui-dist/workspace.js"></script>')
            if native_business:
                assets += ('<link rel="stylesheet" href="/portal-assets/native-business.css">'
                           '<script src="/portal-assets/native-business.js" defer></script>')
            return assets
        if (event and '/manage/' not in request.path and
                (layout_settings.get(event, 'use_custom_css') or layout_settings.get(event, 'theme'))):
            return
        if ((event and self.event_settings.get(event, 'managed')) or
                request.path.startswith(('/user/', '/category/1/manage/'))):
            return ('<meta name="viewport" content="width=device-width, initial-scale=1">'
                    '<link rel="stylesheet" href="/portal-assets/native-workspace.css">'
                    '<script src="/portal-assets/native-workspace.js" defer></script>')

    def management_link(self, sender, event, **kwargs):
        from indico.web.menu import SideMenuItem
        if self.event_settings.get(event, 'managed') and event.can_manage(session.user):
            yield SideMenuItem('yujian_website', '会议网站 · 发布管理', f'/conference/{event.id}/',
                               section='customization', icon='globe')

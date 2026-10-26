"""Matchmaking uses three private, free native registration forms."""
from copy import deepcopy
from datetime import datetime
from uuid import uuid4

from flask import request, session
from flask_pluginengine import render_plugin_template
from werkzeug.exceptions import Conflict, Forbidden, NotFound

from indico.core.db import db
from indico.modules.events import Event
from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.form_fields import RegistrationFormField, RegistrationFormFieldData
from indico.modules.events.registration.models.items import PersonalDataType, RegistrationFormSection
from indico.modules.events.registration.models.registrations import PublishRegistrationsMode
from indico.modules.events.registration.util import create_personal_data_fields
from indico.util.date_time import now_utc
from indico.web.flask.util import url_for
from indico.web.rh import RH

from . import YujianSitePlugin


INTEREST_TYPES = {
    'technology': {
        'title': '技术成果合作登记', 'title_en': 'Technology collaboration',
        'description': '发布研究成果、技术与解决方案，寻找合作伙伴。',
        'description_en': 'Share research and solutions, and find collaboration partners.',
        'fields': [('研究方向及代表成果 / Research and achievements', None),
                   ('拟提供的技术或解决方案 / Technology or solutions offered', None),
                   ('希望对接的对象 / Desired partners', None),
                   ('合作意向 / Cooperation interests',
                    ['联合研发 / Joint R&D', '技术许可或转让 / Licensing or transfer',
                     '成果应用 / Technology application', '融资 / Financing', '项目落地 / Project implementation',
                     '其他 / Other'])]},
    'enterprise': {
        'title': '企业技术需求登记', 'title_en': 'Enterprise technology needs',
        'description': '说明企业技术难题与目标，对接专家和技术能力。',
        'description_en': 'Describe technical challenges and connect with experts.',
        'fields': [('所属行业及具体技术问题 / Industry and technical challenges', None),
                   ('希望达到的技术目标 / Technical objectives', None),
                   ('希望寻找的专家或技术能力 / Expertise sought', None),
                   ('合作意向 / Cooperation interests',
                    ['联合研发 / Joint R&D', '技术咨询 / Technical consulting',
                     '技术引进 / Technology acquisition', '委托开发 / Contract development', '其他 / Other'])]},
    'investment': {
        'title': '投资与项目落地合作登记', 'title_en': 'Investment and project implementation',
        'description': '提供投资与合作资源，对接科技项目、团队和技术企业。',
        'description_en': 'Connect investment and resources with projects, teams and technology companies.',
        'fields': [('机构类型 / Institution type', None),
                   ('重点关注产业方向 / Industries of interest', None),
                   ('可提供合作资源 / Resources offered', None),
                   ('希望寻找科技项目、创业团队或技术企业类型 / Projects, teams or companies sought', None)]},
}


def _mapped_forms(event):
    mapping = deepcopy(YujianSitePlugin.event_settings.get(event, 'interest_forms') or {})
    if not isinstance(mapping, dict) or set(mapping) - set(INTEREST_TYPES):
        raise Conflict('The intent form mapping is invalid; contact the conference administrator.')
    forms = {}
    for kind, info in mapping.items():
        if not isinstance(info, dict) or type(info.get('id')) is not int:
            raise Conflict('The intent form mapping is invalid.')
        form = RegistrationForm.get(info['id'])
        if not form or form.event_id != event.id:
            raise Conflict('The intent form does not belong to this conference.')
        forms[kind] = form
    if len({form.id for form in forms.values()}) != len(forms):
        raise Conflict('Intent forms must be distinct.')
    return mapping, forms


def _add_field(form, section, title, input_type, choices=None):
    field = RegistrationFormField(registration_form=form, parent=section, title=title,
                                  input_type=input_type, is_required=True, is_enabled=True)
    setup = {}
    if choices:
        setup['choices'] = [{'id': str(uuid4()), 'caption': value, 'is_enabled': True,
                             'price': 0, 'places_limit': 0} for value in choices]
    if input_type == 'single_choice':
        setup['item_type'] = 'radiogroup'
    setup = field.field_impl.create_setup_schema(context={'regform': form, 'field': field}).load(setup)
    field.data, versioned = field.field_impl.process_field_data(setup)
    field.current_data = RegistrationFormFieldData(versioned_data=versioned)
    db.session.add(field)


def _create_form(event, kind):
    definition = INTEREST_TYPES[kind]
    form = RegistrationForm(event=event, title=definition['title'],
                            introduction=definition['description'], currency='CNY',
                            private=True, require_login=True, require_user=True, require_captcha=False,
                            base_price=0, tickets_enabled=False, ticket_on_email=False,
                            organizer_notifications_enabled=False, notification_sender_address=None,
                            publish_registrations_public=PublishRegistrationsMode.hide_all,
                            publish_registrations_participants=PublishRegistrationsMode.hide_all,
                            publish_registration_count=False, start_dt=now_utc(), end_dt=event.end_dt)
    db.session.add(form)
    create_personal_data_fields(form)
    personal = {f.personal_data_type: f for f in form.form_items if f.personal_data_type}
    personal[PersonalDataType.first_name].title = '名 / Given name'
    personal[PersonalDataType.last_name].title = '姓 / Family name'
    personal[PersonalDataType.email].title = '电子邮箱 / Email'
    for pd_type, title in ((PersonalDataType.affiliation, '单位 / Organization'),
                           (PersonalDataType.phone, '联系方式 / Phone')):
        field = personal[pd_type]
        field.is_enabled = field.is_required = True
        field.title = title
    section = RegistrationFormSection(registration_form=form, title='对接需求 / Collaboration needs')
    db.session.add(section)
    for title, choices in definition['fields']:
        _add_field(form, section, title, 'multi_choice' if choices else 'textarea', choices)
    _add_field(form, section, '是否计划参会 / Attendance plan', 'single_choice',
               ['计划参会 / Yes', '暂不参会 / No', '尚未确定 / Undecided'])
    db.session.flush()
    return form


def sync_interest_forms(event, content):
    """Call in the authorized content-save transaction, never from a GET."""
    db.session.query(Event).filter_by(id=event.id).with_for_update().one()
    # Read settings after acquiring the event lock so simultaneous enables cannot create duplicates.
    YujianSitePlugin.event_settings._flush_cache()
    mapping, forms = _mapped_forms(event)
    enabled = content.get('matchmaking', {}).get('enabled', False)
    changed = False
    if enabled:
        set_feature_enabled(event, 'registration', True)
        for kind in INTEREST_TYPES:
            if kind not in mapping:
                form = _create_form(event, kind)
                mapping[kind] = {'id': form.id}
                forms[kind] = form
                changed = True
    for kind, form in forms.items():
        info = mapping[kind]
        pause = info.get('paused')
        if enabled and pause:
            if (not form.is_deleted and form.start_dt is None and form.end_dt and
                    form.end_dt.isoformat() == pause['closed_at']):
                form.start_dt = datetime.fromisoformat(pause['start']) if pause['start'] else None
                form.end_dt = datetime.fromisoformat(pause['end']) if pause['end'] else None
            info.pop('paused')
            changed = True
        elif not enabled and form.is_scheduled and not form.has_ended and not pause:
            closed_at = now_utc()
            info['paused'] = {'start': form.start_dt.isoformat(),
                              'end': form.end_dt.isoformat() if form.end_dt else None,
                              'closed_at': closed_at.isoformat()}
            form.start_dt = None
            form.end_dt = closed_at
            changed = True
    if changed:
        YujianSitePlugin.event_settings.set(event, 'interest_forms', mapping)
    return mapping


def suppress_interest_notifications(sender, func, args, ctx, RETURN_NONE, **kwargs):
    """Suppress native automatic email only for our mapped intent forms."""
    registration = args.arguments.get('registration')
    if registration:
        mapping = YujianSitePlugin.event_settings.get(registration.event, 'interest_forms') or {}
        if any(isinstance(info, dict) and info.get('id') == registration.registration_form_id
               for info in mapping.values()):
            return RETURN_NONE


def protect_interest_submission(sender, rh, **kwargs):
    """Native invitations bypass opening dates; the website switch must still apply."""
    if sender.__name__ != 'RHRegistrationForm' or request.method != 'POST':
        return
    form = rh.regform
    settings = YujianSitePlugin.event_settings
    mapping = settings.get(form.event, 'interest_forms') or {}
    if not any(isinstance(info, dict) and info.get('id') == form.id for info in mapping.values()):
        return
    content = settings.get(form.event, 'content') or {}
    if not content.get('matchmaking', {}).get('enabled'):
        raise Forbidden('意向登记已关闭 / Intent registration is closed.')
    if not session.user or session.user.is_deleted or session.user.is_blocked or session.user.is_pending:
        raise Forbidden('请先登录经验证的账号 / A verified account is required.')


class RHInterest(RH):
    def _process_args(self):
        from .conference_accounts import accessible_conference
        self.event = accessible_conference(request.view_args['event_id'])

    def _process(self):
        from .conference_accounts import account_links
        settings = YujianSitePlugin.event_settings
        content = settings.get(self.event, 'content') or {}
        if not content.get('matchmaking', {}).get('enabled'):
            raise NotFound()
        mapping, forms = _mapped_forms(self.event)
        options = []
        for kind, definition in INTEREST_TYPES.items():
            form = forms.get(kind)
            options.append({**definition, 'available': bool(form and form.is_active),
                            'url': url_for('event_registration.display_regform', form.locator.token)
                            if form and not form.is_deleted else None})
        result = render_plugin_template('interest.html', event=self.event, options=options,
                                         account=account_links(self.event, request.path),
                                         introduction=content['matchmaking'])
        return result, 200, {'Cache-Control': 'private, no-store'}


def register_routes(bp):
    bp.add_url_rule('/event/<int:event_id>/interest/', 'interest', RHInterest, methods=('GET',))

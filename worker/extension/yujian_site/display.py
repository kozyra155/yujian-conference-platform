"""Branded views, reached only after the native request's permission checks."""
import re
from math import ceil
from copy import deepcopy
from datetime import date, datetime, time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from flask import make_response, session
from flask_pluginengine import render_plugin_template
from indico.modules.events.layout import layout_settings
from indico.modules.events.layout.util import menu_entries_for_event
from indico.modules.events.layout.views import WPMenuEdit
from indico.modules.events.layout.models.menu import MenuEntry
from indico.util.i18n import get_current_locale
from .conference_accounts import account_links

CHOICE_LABELS = {
    '论文与报告': 'Papers and presentations', '学术海报展示': 'Academic posters', '科技成果展板': 'Research achievement displays',
    '成果路演': 'Project pitches', '实物或样机展示': 'Products and prototypes', '软件或系统演示': 'Software and system demos',
    '线上成果展示': 'Online showcases', '产业合作对接': 'Industry collaboration', '暂不确定': 'To be determined',
    '企业技术需求发布': 'Enterprise technology needs', '专题论坛': 'Thematic forums', '科技成果产业推介': 'Research to industry presentations',
    '一对一预约洽谈': 'One-to-one meetings', '企业及产业园区参访': 'Company and industrial park visits',
    '高校/科研院所': 'Universities and research institutes', '企业技术负责人': 'Enterprise technology leaders',
    '产业园区与协会': 'Industrial parks and associations', '投资与服务机构': 'Investment and service organizations',
    '高水平专家交流': 'Exchange with leading experts', '精准供需对接': 'Targeted needs matching',
    '期刊合作与论文交流': 'Journal collaboration and paper exchange', '地方特色产业聚焦': 'Focus on local industries',
    '科技成果转化与项目落地': 'Research commercialization and project delivery', '多形式科技成果展示': 'Research showcases in multiple formats',
    '人才引进与研发合作': 'Talent recruitment and R&D collaboration', '科技金融与投融资对接': 'Technology finance and investment connections',
}
AUDIENCE_DESCRIPTIONS = {
    '高校/科研院所': ('高校教师、科研人员、研究生及科研团队', 'University faculty, researchers, postgraduate students and research teams'),
    '企业技术负责人': ('企业高管、技术总监、研发与创新负责人', 'Enterprise executives, technology directors and R&D and innovation leaders'),
    '产业园区与协会': ('地方政府、产业园区、行业协会及相关机构', 'Local governments, industrial parks, industry associations and related organizations'),
    '投资与服务机构': ('投资机构、金融机构、科技服务机构', 'Investment institutions, financial institutions and technology service organizations'),
}


def _date_countdown(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return None
    try:
        return (date.fromisoformat(value) - datetime.now(ZoneInfo('Asia/Shanghai')).date()).days
    except ValueError:
        return None


def _conference_countdown(event, settings):
    if not settings.get('enabled'):
        return None
    zone = ZoneInfo('Asia/Shanghai')
    configured = settings.get('target_date', '')
    target_date = date.fromisoformat(configured) if configured else event.start_dt.astimezone(zone).date()
    target = datetime.combine(target_date, time.min, tzinfo=zone)
    now = datetime.now(zone)
    remaining = max(0, ceil((target - now).total_seconds()))
    days, remainder = divmod(remaining, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return dict(target=target.isoformat(), now=now.isoformat(), days=days, hours=hours, minutes=minutes,
                seconds=seconds, expired=remaining == 0, is_conference=not configured)


def _safe_public_url(value):
    if not isinstance(value, str) or any(ord(c) < 33 for c in value) or '\\' in value:
        return ''
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ''
    return value if (parsed.scheme in {'http', 'https', 'mailto'} or
                     (value.startswith('/') and not value.startswith('//'))) else ''


def _public_navigation(entries, user, blocked_names=()):
    """Keep native hierarchy; a hidden or restricted parent hides its entire subtree."""
    result = []
    for entry in entries:
        if not entry.is_visible or not entry.can_access(user) or entry.name in blocked_names:
            continue
        if entry.is_separator:
            if result and not result[-1]['separator']:
                result.append({'separator': True, 'title': '', 'children': []})
            continue
        children = _public_navigation(entry.children, user, blocked_names)
        url = _safe_public_url(entry.url)
        if url or children:
            result.append({'id': str(entry.id), 'title': str(entry.localized_title), 'url': url,
                           'new_tab': entry.new_tab, 'separator': False, 'children': children,
                           'page_id': entry.page_id, 'name': entry.name})
    if result and result[-1]['separator']:
        result.pop()
    return result


def _complete_actions(event, content):
    actions = []
    for key, zh, en in [('registration', '会议报名', 'Registration'),
                        ('submission', '会议投稿', 'Abstract submission')]:
        action = content['actions'][key]
        if not action['enabled']:
            continue
        if action['mode'] == 'external':
            url = _safe_public_url(action['url'])
            if url:
                actions.append(dict(key=key, zh=zh, en=en, url=url, state_zh='', state_en='', native=False,
                                    text=action.get('text', ''), text_en=action.get('text_en', '')))
            continue
        feature = 'registration' if key == 'registration' else 'abstracts'
        if not event.has_feature(feature):
            continue
        if key == 'registration':
            available = any(not form.private and form.is_active for form in event.registration_forms)
            url = f'/event/{event.id}/registrations/' if available else ''
            state_zh, state_en = ('', '') if available else ('报名尚未开放', 'Registration is not open')
        else:
            url = f'/event/{event.id}/abstracts/'
            state_zh, state_en = ('投稿开放中', 'Submissions open') if event.cfa.is_open else ('投稿尚未开放', 'Submissions are closed')
        if url and not session.user:
            url = account_links(event, url)['login_url']
        actions.append(dict(key=key, zh=zh, en=en, url=url, state_zh=state_zh, state_en=state_en, native=True,
                            text=action.get('text', ''), text_en=action.get('text_en', '')))
    return actions


def _conference_entry(event, actions=None):
    if actions is None:
        actions = _complete_actions(event, {'actions': {'registration': {'enabled': True, 'mode': 'native'},
                                                       'submission': {'enabled': False}}})
    registration = next((item for item in actions if item['key'] == 'registration'), None)
    if not registration or not registration['url']:
        return {'guest_url': '', 'member_url': '', 'state_zh': '报名尚未开放', 'state_en': 'Registration is not open'}
    native = f'/event/{event.id}/registrations/'
    return {'guest_url': account_links(event, native)['login_url'] if registration['native'] else registration['url'],
            'member_url': native if registration['native'] else registration['url'], 'state_zh': '', 'state_en': ''}


def _render_complete_conference(event, page, plugin, theme_override=None):
    from .site_content import clean_rich_html, get_site_content
    content = deepcopy(get_site_content(event))
    if theme_override is not None:
        content['theme'] = theme_override
    # Only enabled, meaningful public items reach the template, including nested unit groups.
    for key, field in [('speakers', 'name'), ('news', 'title'), ('dates', 'date')]:
        content[key] = [item for item in content[key] if item.get('enabled', True) and
                        (item.get(field) or item.get(field + '_en'))]
    for item in content['dates']:
        item['countdown'] = _date_countdown(item['date'])
    groups = []
    for group in content['organizations']:
        if not group.get('enabled', True):
            continue
        group['items'] = [item for item in group.get('items', []) if item.get('enabled', True) and
                          any(item.get(key) for key in ('name', 'name_en', 'image', 'images', 'description', 'description_en'))]
        if group['items']:
            groups.append(group)
    content['organizations'] = groups
    committees = []
    for group in content['committees']:
        if not group.get('enabled', True):
            continue
        group['members'] = [member for member in group.get('members', []) if member.get('enabled', True) and
                            any(member.get(key) for key in ('name', 'name_en', 'affiliation', 'affiliation_en'))]
        if group['members']:
            committees.append(group)
    content['committees'] = committees
    for key, fields in [('topics', ('title', 'title_en', 'keywords', 'keywords_en')),
                        ('industry', ('title', 'title_en', 'description', 'description_en', 'goal', 'goal_en', 'cooperation', 'cooperation_en'))]:
        content[key] = [item for item in content[key] if item.get('enabled', True) and any(item.get(field) for field in fields)]
    for key in ('html', 'html_en'):
        content['contact'][key] = clean_rich_html(content['contact'].get(key, ''))
    available = {'introduction': bool(event.description or content['introduction_en'] or content['introduction_images']),
                 'speakers': bool(content['speakers']), 'news': bool(content['news']),
                 'notices': content['notices']['enabled'] and bool(content['notices']['text'] or content['notices']['text_en']),
                 'venue': content['venue']['enabled'] and bool(content['venue']['description'] or content['venue']['description_en'] or content['venue']['images']),
                 'committees': bool(content['committees']),
                 'topics': bool(content['topics'] or content['topic_note'] or content['topic_note_en']),
                 'industry': bool(content['industry']), 'showcase': bool(content['showcase']),
                 'audience': bool(content['audience']), 'highlights': bool(content['highlights']),
                 'matchmaking': content['matchmaking']['enabled'] and bool(content['matchmaking']['text'] or
                                 content['matchmaking']['text_en'] or content['matchmaking']['activities'])}
    for key in ('registration', 'submission'):
        available[key + '_info'] = bool(content['actions'][key]['text'] or content['actions'][key]['text_en'])
    sections = [item['key'] for item in content['sections'] if item['enabled'] and available.get(item['key'])]
    actions = _complete_actions(event, content)
    # Canonical content pages provide navigation; configured business actions live in the sidebar.
    blocked = ('registration', 'call_for_abstracts')
    # Native menu rendering backfills missing entries in a separate transaction; previews must only read.
    menu_entries = (MenuEntry.get_for_event(event) if theme_override is not None and
                    layout_settings.get(event, 'use_custom_menu') else menu_entries_for_event(event))
    navigation = _public_navigation(menu_entries, session.user, blocked)
    accent = content['theme']['accent']
    accent = accent if re.fullmatch(r'#[0-9a-fA-F]{6}', accent or '') else '#fa7d4b'
    layout = content['theme'].get('layout', 'simple-1')
    layout = layout if layout in ('simple-1', 'simple-2') else 'simple-1'
    result = make_response(render_plugin_template(
        'complete-conference.html', event=event, page=page, content=content, sections=sections,
        countdown=_conference_countdown(event, content['countdown']) if not page else None,
        navigation=navigation, actions=actions, participation_entry=_conference_entry(event, actions),
        choice_labels=CHOICE_LABELS, audience_descriptions=AUDIENCE_DESCRIPTIONS,
        matchmaking_intent_url=f'/event/{event.id}/interest/' if content['matchmaking']['enabled'] else '',
        account=account_links(event, f'/event/{event.id}/page/{page.id}' if page else None), accent=accent, appearance_layout=layout,
        language='en' if str(get_current_locale()).startswith('en') else 'zh',
        can_manage=event.can_manage(session.user), published=plugin.event_settings.get(event, 'published'),
        announcement=layout_settings.get(event, 'announcement') if layout_settings.get(event, 'show_announcement') else None))
    result.headers['Cache-Control'] = 'private, no-store'
    return result


class WPMeetMenuEdit(WPMenuEdit):
    template_prefix = ''


def render_menu_editor(event):
    from . import YujianSitePlugin
    enabled = layout_settings.get(event, 'use_custom_menu')
    menu = menu_entries_for_event(event) if enabled else None
    overview_id = next((entry.id for entry in menu or [] if entry.name == 'overview'), None)
    return WPMeetMenuEdit.render_template('yujian_site:menu-editor.html', event, menu=menu,
                                         custom_menu_enabled=enabled, overview_id=overview_id,
                                         published=YujianSitePlugin.event_settings.get(event, 'published'))


def render_workspace(mode):
    result = make_response(render_plugin_template('builder.html', mode=mode, event=None))
    result.headers['Cache-Control'] = 'private, no-store'
    return result


def render_conference(event, page=None, theme_override=None):
    from . import YujianSitePlugin
    if theme_override is not None or YujianSitePlugin.event_settings.get(event, 'template') == 'academic-full':
        return _render_complete_conference(event, page, YujianSitePlugin, theme_override)
    # Check parents as well: restricted child pages must not leak through excerpts or navigation.
    def visible(entries):
        result = []
        for entry in entries:
            if entry.is_visible and not entry.is_separator:
                result.append(entry)
                result.extend(visible(entry.children))
        return result

    entries = visible(menu_entries_for_event(event))
    pages = [entry for entry in entries if entry.is_page]
    notices = next((entry for entry in pages if entry.title == '重要通知'), None)
    contact = next((entry for entry in pages if entry.title == '联系我们'), None)
    color = layout_settings.get(event, 'header_background_color')
    color = color if re.fullmatch(r'#[0-9a-fA-F]{6}', color or '') else '#194e7b'
    text_color = layout_settings.get(event, 'header_text_color')
    text_color = text_color if re.fullmatch(r'#[0-9a-fA-F]{6}', text_color or '') else '#ffffff'
    result = make_response(render_plugin_template(
        'conference-site.html', event=event, page=page, entries=entries, pages=pages,
        notices=notices, contact=contact, participation_entry=_conference_entry(event),
        account=account_links(event, f'/event/{event.id}/page/{page.id}' if page else None), primary_color=color, heading_color=text_color,
        logo_as_banner=layout_settings.get(event, 'header_logo_as_banner'),
        can_manage=event.can_manage(session.user),
        published=YujianSitePlugin.event_settings.get(event, 'published'),
        announcement=layout_settings.get(event, 'announcement') if layout_settings.get(event, 'show_announcement') else None))
    # A visible page can still be a draft preview or contain user-specific navigation.
    result.headers['Cache-Control'] = 'private, no-store'
    return result

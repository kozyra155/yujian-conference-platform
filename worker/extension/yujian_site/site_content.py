"""Structured homepage content, native pages, and validated image attachments."""
import copy
import io
import re
import warnings
from datetime import date
from html import escape as html_escape
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

from flask import session
from PIL import Image, UnidentifiedImageError
from werkzeug.exceptions import BadRequest

from indico.core import signals
from indico.core.db import db
from indico.core.db.sqlalchemy.links import LinkType
from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.modules.attachments.models.attachments import Attachment, AttachmentFile, AttachmentType
from indico.modules.attachments.models.folders import AttachmentFolder
from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.layout.models.menu import EventPage, MenuEntry, MenuEntryType
from indico.modules.events.models.settings import EventSetting
from indico.util.string import sanitize_html
from markupsafe import escape

from .appearances import APPEARANCES, validate_theme

TEMPLATES = ('academic-full', 'academic', 'industry')
ASSET_FOLDER = 'Yujian website images'
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
LEGACY_SECTIONS = ('introduction', 'speakers', 'news', 'notices', 'venue')
SECTIONS = (*LEGACY_SECTIONS, 'committees', 'topics', 'industry', 'showcase', 'matchmaking', 'audience', 'highlights',
            'registration_info', 'submission_info')
SHOWCASE = ('论文与报告', '学术海报展示', '科技成果展板', '成果路演', '实物或样机展示', '软件或系统演示', '线上成果展示', '产业合作对接', '暂不确定')
ACTIVITIES = ('企业技术需求发布', '专题论坛', '科技成果产业推介', '一对一预约洽谈', '企业及产业园区参访')
AUDIENCE = ('高校/科研院所', '企业技术负责人', '产业园区与协会', '投资与服务机构')
HIGHLIGHTS = ('高水平专家交流', '精准供需对接', '期刊合作与论文交流', '企业及产业园区参访', '地方特色产业聚焦', '企业技术需求发布', '科技成果转化与项目落地', '多形式科技成果展示', '人才引进与研发合作', '科技金融与投融资对接')


def default_content(event):
    return {
        'banner': {'image': '', 'image_en': '', 'title': '', 'title_en': '', 'subtitle': '',
                   'subtitle_en': '', 'show_title': True},
        'theme': {'layout': 'simple-1', 'accent': '#fa7d4b'}, 'introduction_en': '',
        'introduction_images': [],
        'sections': [{'key': key, 'enabled': key in LEGACY_SECTIONS} for key in SECTIONS],
        'speakers': [], 'news': [],
        'committees': [], 'topics': [], 'topic_note': '', 'topic_note_en': '', 'industry': [],
        'showcase': [], 'audience': [], 'highlights': [],
        'matchmaking': {'text': '', 'text_en': '', 'activities': [], 'enabled': False},
        'countdown': {'enabled': False, 'target_date': ''},
        'dates': [{'label': '会议日期', 'label_en': 'Conference dates',
                   'date': f'{event.start_dt_local:%Y-%m-%d} – {event.end_dt_local:%Y-%m-%d}', 'end_date': '', 'enabled': True}],
        'organizations': [{'title': title, 'title_en': title_en, 'enabled': True, 'items': []}
                          for title, title_en in [('主办单位', 'Organizers'), ('专业技术支持', 'Technical support'),
                                                  ('产业支持', 'Industry support'), ('期刊支持', 'Journal support')]],
        'contact': {'name': '', 'name_en': '', 'phone': '', 'email': '', 'address': '',
                    'address_en': '', 'html': '', 'html_en': '', 'images': [], 'enabled': True},
        'notices': {'text': '', 'text_en': '', 'enabled': True},
        'venue': {'description': '', 'description_en': '', 'images': [], 'enabled': True},
        'actions': {name: {'enabled': False, 'mode': 'native', 'url': '', 'text': '', 'text_en': ''}
                    for name in ('registration', 'submission')},
    }


def _settings(event):
    # Read the current transaction directly; settings proxies may have been cached before a row lock.
    return dict(db.session.query(EventSetting.name, EventSetting.value).filter_by(
        event_id=event.id, module='plugin_yujian_site').all())


def get_site_content(event):
    """Return independent content defaults without writing settings for older events."""
    defaults = default_content(event)
    saved = _settings(event).get('content') or {}
    for key, value in saved.items():
        if key in defaults:
            if isinstance(defaults[key], dict) and isinstance(value, dict):
                defaults[key].update(copy.deepcopy(value))
            else:
                defaults[key] = copy.deepcopy(value)
    # Older saves may contain partial nested records; fill absent fields without persisting a migration.
    def fill(items, values):
        return [copy.deepcopy(values) | item for item in items if isinstance(item, dict)]
    defaults['speakers'] = fill(defaults['speakers'], dict.fromkeys(
        ('name', 'name_en', 'affiliation', 'affiliation_en', 'topic', 'topic_en', 'role', 'role_en', 'bio', 'bio_en', 'image'), '') | {'enabled': True})
    defaults['news'] = fill(defaults['news'], dict.fromkeys(('title', 'title_en', 'date', 'body', 'body_en', 'url'), '') | {'enabled': True})
    defaults['dates'] = fill(defaults['dates'], {'label': '', 'label_en': '', 'date': '', 'end_date': '', 'enabled': True})
    defaults['organizations'] = fill(defaults['organizations'], {'title': '', 'title_en': '', 'enabled': True, 'items': []})
    for group in defaults['organizations']:
        group['items'] = fill(group['items'], dict.fromkeys(('name', 'name_en', 'image', 'url', 'description', 'description_en'), '') | {'images': [], 'enabled': True})
    for key in ('registration', 'submission'):
        defaults['actions'][key] = default_content(event)['actions'][key] | defaults['actions'].get(key, {})
    present = {section.get('key') for section in defaults['sections']}
    defaults['sections'].extend({'key': key, 'enabled': False} for key in SECTIONS if key not in present)
    return defaults


def get_content_payload(event):
    settings = _settings(event)
    return {'template': settings.get('template', 'academic'), 'revision': settings.get('content_revision', 0),
            'content': get_site_content(event), 'appearances': copy.deepcopy(APPEARANCES),
            'registration_url': f'/event/{event.id}/registrations/',
            'submission_url': f'/event/{event.id}/abstracts/'}


def _safe_url(value, allow_mailto=False):
    if not value:
        return
    decoded = value
    for _ in range(3):
        decoded = unquote(decoded)
    if (any(c.isspace() for c in value) or any(ord(c) < 32 or ord(c) == 127 for c in decoded)
            or '\\' in decoded or decoded != decoded.lstrip()):
        raise BadRequest('Invalid link URL.')
    parsed = urlsplit(decoded)
    if any(c.isspace() for c in parsed.netloc):
        raise BadRequest('Invalid link URL.')
    if decoded.startswith('/') and not decoded.startswith('//') and not parsed.scheme and not parsed.netloc:
        return
    if parsed.scheme.lower() in ('http', 'https') and parsed.netloc and not parsed.username and not parsed.password:
        return
    if allow_mailto and parsed.scheme.lower() == 'mailto' and parsed.path and not parsed.netloc:
        return
    raise BadRequest('Links must use HTTP(S) or a safe absolute site path.')


def _image_urls(event):
    attachments = Attachment.query.join(Attachment.folder).filter(
        AttachmentFolder.event_id == event.id, AttachmentFolder.title == ASSET_FOLDER,
        AttachmentFolder.link_type == LinkType.event, AttachmentFolder.linked_event_id == event.id,
        AttachmentFolder.is_hidden, ~AttachmentFolder.is_always_visible,
        AttachmentFolder.protection_mode == ProtectionMode.inheriting,
        ~AttachmentFolder.is_deleted, ~Attachment.is_deleted,
        Attachment.type == AttachmentType.file).all()
    return {a.download_url for a in attachments if a.file and a.file.content_type in
            ('image/png', 'image/jpeg', 'image/webp') and a.can_access(session.user)}


def clean_rich_html(value):
    """Keep formatted contact text; images belong in the validated conference gallery."""
    media_tags = {'img', 'video', 'audio', 'source', 'track', 'iframe', 'object', 'embed', 'picture'}
    class SafeLinks(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.parts = []

        def handle_starttag(self, tag, attrs):
            if tag in media_tags:
                return
            safe = []
            for key, value in attrs:
                if key in ('href', 'src'):
                    try:
                        _safe_url(value or '', allow_mailto=key == 'href')
                    except (BadRequest, ValueError):
                        continue
                safe.append(f' {key}="{html_escape(value or "", quote=True)}"')
            self.parts.append(f'<{tag}{"".join(safe)}>')

        def handle_endtag(self, tag):
            if tag not in media_tags:
                self.parts.append(f'</{tag}>')

        def handle_data(self, data):
            self.parts.append(data)

        def handle_entityref(self, name):
            self.parts.append(f'&{name};')

        def handle_charref(self, name):
            self.parts.append(f'&#{name};')

    parser = SafeLinks()
    parser.feed(str(sanitize_html(value)))
    return ''.join(parser.parts)


def validate_content(event, data):
    """Validate at the trust boundary and identify the exact editable field on errors."""
    image_urls = _image_urls(event)

    def fail(path, message):
        raise BadRequest(f'{path or "content"}: {message}')

    def obj(value, schema, path='', required=()):
        if not isinstance(value, dict):
            fail(path, '请填写一个内容对象。')
        unknown = set(value) - set(schema)
        if unknown:
            fail(f'{path}.{sorted(unknown)[0]}' if path else sorted(unknown)[0], '不支持的字段。')
        for key in required:
            if key not in value:
                fail(f'{path}.{key}', '缺少必填字段。')
        return {key: rule(value.get(key, copy.deepcopy(default)), f'{path}.{key}' if path else key)
                for key, (default, rule) in schema.items()}

    def string(limit=500):
        def validate(value, path):
            if not isinstance(value, str) or len(value) > limit or '\x00' in value:
                fail(path, f'请输入不超过 {limit} 个字符的文字。')
            return value
        return validate

    def boolean(value, path):
        if type(value) is not bool:
            fail(path, '开关必须为 true 或 false。')
        return value

    def image(value, path):
        value = string(2000)(value, path)
        if value and value not in image_urls:
            fail(path, '图片必须是本会议已上传且有权访问的 PNG、JPEG 或 WebP 图片。')
        return value

    def link(value, path, mailto=False):
        value = string(2000)(value, path)
        try:
            _safe_url(value, mailto)
        except (BadRequest, ValueError):
            fail(path, '链接须为完整 HTTP(S) 地址或站内绝对路径，不能包含空格、控制字符或反斜杠。')
        return value

    def choice(values):
        def validate(value, path):
            if not isinstance(value, str) or value not in values:
                fail(path, '请选择列表中的有效选项。')
            return value
        return validate

    def array(rule, limit=50, unique=False):
        def validate(value, path):
            if not isinstance(value, list) or len(value) > limit:
                fail(path, f'最多可填写 {limit} 项。')
            result = [rule(item, f'{path}[{i}]') for i, item in enumerate(value)]
            if unique and len(set(result)) != len(result):
                fail(path, '选项不能重复。')
            return result
        return validate

    def entries(schema, limit=50):
        return array(lambda value, path: obj(value, schema, path, ('enabled',)), limit)

    def fields(*names, limit=500):
        return {name: ('', string(limit)) for name in names}

    def nested(schema):
        return lambda value, path: obj(value, schema, path)

    def rich(value, path):
        return clean_rich_html(string(20000)(value, path))

    def theme(value, path):
        if not isinstance(value, dict) or set(value) - {'layout', 'accent'}:
            fail(path, '外观仅支持布局与主题颜色。')
        if not isinstance(value.get('layout', 'simple-1'), str) or value.get('layout', 'simple-1') not in ('simple-1', 'simple-2'):
            fail(f'{path}.layout', '请选择有效的外观布局。')
        if not isinstance(value.get('accent', '#fa7d4b'), str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value.get('accent', '#fa7d4b')):
            fail(f'{path}.accent', '主题颜色须使用六位十六进制格式，例如 #fa7d4b。')
        return validate_theme(value)

    def industry_text(limit=5000):
        def validate(value, path):
            value = string(limit)(value, path)
            prohibited = (r'(?:[a-z][a-z0-9+.-]*://|www\.|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}'
                          r'|(?<!\d)1[3-9]\d[- ]?\d{4}[- ]?\d{4}(?!\d)'
                          r'|(?<!\d)0\d{2,3}[- ]?\d{7,8}(?!\d)'
                          r'|\+\d{1,3}[- ]?\(?\d[\d ()-]{6,}\d'
                          r'|\b(?:400|800)[- ]?\d{3}[- ]?\d{4}\b|\b\d{3}[- ]\d{3}[- ]\d{4}\b'
                          r'|\b(?:[a-z0-9-]+\.)+(?:com|cn|org|net|edu|gov)(?:\b|/))')
            if re.search(prohibited, value, re.I):
                fail(path, '产业需求仅填写研究方向与合作目标，请勿填写企业名称、网址、邮箱或电话号码。')
            return value
        return validate

    enabled = {'enabled': (True, boolean)}
    images = {'images': ([], array(image, 20))}
    speaker = fields('name', 'name_en', 'affiliation', 'affiliation_en', 'topic', 'topic_en')
    speaker |= fields('role', 'role_en', limit=200) | fields('bio', 'bio_en', limit=1000)
    speaker.update(image=('', image), **enabled)
    news = fields('title', 'title_en', 'date') | fields('body', 'body_en', limit=10000)
    news.update(url=('', link), **enabled)
    organization_item = fields('name', 'name_en') | fields('description', 'description_en', limit=300)
    organization_item |= {'image': ('', image), 'url': ('', link)} | enabled | images
    organization = fields('title', 'title_en', limit=300) | enabled | {'items': ([], entries(organization_item))}
    banner = fields('title', 'title_en', 'subtitle', 'subtitle_en')
    banner.update(image=('', image), image_en=('', image), show_title=(True, boolean))
    action = lambda mailto: {'enabled': (False, boolean), 'mode': ('native', choice(('native', 'external'))),
                            'url': ('', lambda value, path: link(value, path, mailto))} | fields('text', 'text_en', limit=10000)
    member = fields('name', 'name_en', 'affiliation', 'affiliation_en') | enabled
    committee = fields('title', 'title_en', limit=300) | enabled | {'members': ([], entries(member, 100))}
    topic = fields('title', 'title_en', limit=300) | fields('keywords', 'keywords_en', limit=5000) | enabled
    industry = {name: ('', industry_text(300 if name in ('title', 'title_en') else 5000))
                for name in ('title', 'title_en', 'description', 'description_en', 'goal', 'goal_en', 'cooperation', 'cooperation_en')} | enabled
    defaults = default_content(event)
    schema = {
        'banner': (defaults['banner'], nested(banner)),
        'theme': (defaults['theme'], theme),
        'introduction_en': ('', string(20000)), 'introduction_images': ([], array(image, 20)),
        'sections': (defaults['sections'], entries({'key': ('introduction', choice(SECTIONS)), **enabled}, len(SECTIONS))),
        'speakers': ([], entries(speaker)), 'news': ([], entries(news, 100)),
        'dates': (defaults['dates'], entries(fields('label', 'label_en', 'date', 'end_date') | enabled)),
        'countdown': (defaults['countdown'], nested({'enabled': (False, boolean), 'target_date': ('', string(10))})),
        'organizations': (defaults['organizations'], entries(organization, 20)),
        'contact': (defaults['contact'], nested(fields('name', 'name_en', 'phone', 'email', 'address', 'address_en') |
                                              {'html': ('', rich), 'html_en': ('', rich)} | enabled | images)),
        'notices': (defaults['notices'], nested(fields('text', 'text_en', limit=10000) | enabled)),
        'venue': (defaults['venue'], nested(fields('description', 'description_en', limit=10000) | enabled | images)),
        'actions': (defaults['actions'], nested({name: (defaults['actions'][name], nested(action(name == 'submission')))
                                               for name in ('registration', 'submission')})),
        'committees': ([], entries(committee, 20)), 'topics': ([], entries(topic, 30)),
        'topic_note': ('', string(2000)), 'topic_note_en': ('', string(2000)),
        'industry': ([], entries(industry, 30)), 'showcase': ([], array(choice(SHOWCASE), len(SHOWCASE), True)),
        'audience': ([], array(choice(AUDIENCE), len(AUDIENCE), True)),
        'highlights': ([], array(choice(HIGHLIGHTS), len(HIGHLIGHTS), True)),
        'matchmaking': (defaults['matchmaking'], nested(fields('text', 'text_en', limit=10000) |
                         {'activities': ([], array(choice(ACTIVITIES), len(ACTIVITIES), True)), 'enabled': (False, boolean)})),
    }
    content = obj(data, schema)
    if content['countdown']['target_date']:
        try:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', content['countdown']['target_date']):
                raise ValueError
            date.fromisoformat(content['countdown']['target_date'])
        except ValueError:
            fail('countdown.target_date', '倒计时目标日期须使用有效的 YYYY-MM-DD 格式。')
    if len({item['key'] for item in content['sections']}) != len(content['sections']):
        fail('sections', '首页板块不能重复。')
    for i, item in enumerate(content['dates']):
        if item['end_date']:
            parsed = {}
            for key in ('date', 'end_date'):
                try:
                    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', item[key]):
                        raise ValueError
                    parsed[key] = date.fromisoformat(item[key])
                except ValueError:
                    fail(f'dates[{i}].{key}', '日期范围须使用有效的 YYYY-MM-DD 格式。')
            if parsed['end_date'] < parsed['date']:
                fail(f'dates[{i}].end_date', '结束日期不能早于开始日期。')
    return content


def ensure_complete_site(event, new=False):
    """Add absent native pages without changing existing titles, text, ordering, or ACLs."""
    entries = MenuEntry.query.filter_by(event_id=event.id).all()
    titles = {entry.title: entry for entry in entries}
    root_position = max((entry.position for entry in entries if entry.parent_id is None), default=0)

    def add(title, text, parent=None):
        nonlocal root_position
        if title in titles:
            return titles[title]
        if parent is None:
            root_position += 1
            position = root_position
        else:
            position = max((child.position for child in parent.children), default=-1) + 1
        page = EventPage(event=event, html=f'<h2>{escape(title)}</h2><p>{escape(text)}</p>')
        entry = MenuEntry(event=event, type=MenuEntryType.page, title=title, page=page,
                          parent=parent, position=position, is_enabled=True)
        db.session.add(entry)
        titles[title] = entry
        return entry

    organization = add('会议组织', '请维护会议组织信息。')
    add('组委会', '请填写组委会成员及所属单位。', organization)
    add('专题召集人', '请填写专题及召集人信息。', organization)
    for title, text in [('会议日程', '请填写会议日程。'), ('注册缴费', '请由主办方配置原生报名表及缴费说明。'),
                        ('会议投稿', '请由主办方配置投稿规则与开放时间。'), ('会议酒店', '请填写会议酒店及预订方式。'),
                        ('考察活动', '请填写考察活动安排。'), ('历届会议', '请填写历届会议信息。'),
                        ('联系我们', '请填写主办方对外联系方式。')]:
        add(title, text)
    for name in ('registration', 'abstracts'):
        set_feature_enabled(event, name, True)
    if new:
        navigation = ['会议首页', '会议组织', '会议日程', '注册缴费', '会议投稿',
                      '会议酒店', '考察活动', '历届会议', '联系我们']
        # Only a newly created full site receives template ordering; upgrades preserve every owner choice.
        for entry in titles.values():
            if entry.parent is None and entry.parent_id is None:
                entry.is_enabled = entry.title in navigation
                if entry.is_enabled:
                    entry.position = navigation.index(entry.title)


def upload_image(event, upload):
    raw = upload.stream.read(MAX_IMAGE_BYTES + 1)
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise BadRequest('Images must be no larger than 5 MiB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as img:
                image_format = img.format
                if image_format not in ('PNG', 'JPEG', 'WEBP') or img.width * img.height > MAX_IMAGE_PIXELS:
                    raise BadRequest('Only PNG/JPEG/WebP images up to 20 million pixels are accepted.')
                img.verify()
            with Image.open(io.BytesIO(raw)) as img:
                img.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise BadRequest('The uploaded file is not a valid image.') from None
    extension, content_type = {'PNG': ('png', 'image/png'), 'JPEG': ('jpg', 'image/jpeg'),
                               'WEBP': ('webp', 'image/webp')}[image_format]
    folder = AttachmentFolder.query.filter_by(
        event_id=event.id, linked_event_id=event.id, link_type=LinkType.event, title=ASSET_FOLDER,
        is_hidden=True, is_always_visible=False, is_deleted=False,
        protection_mode=ProtectionMode.inheriting).first()
    if folder is None:
        # A same-name owner folder remains untouched; only our hidden inheriting folder is reusable.
        folder = AttachmentFolder(object=event, title=ASSET_FOLDER, is_always_visible=False, is_hidden=True,
                                  protection_mode=ProtectionMode.inheriting)
    attachment = Attachment(folder=folder, user=session.user, title=f'Website image.{extension}', type=AttachmentType.file)
    attachment.file = AttachmentFile(user=session.user, filename=f'website-image.{extension}', content_type=content_type)
    attachment.file.save(io.BytesIO(raw))
    db.session.add(attachment)
    db.session.flush()
    signals.attachments.attachment_created.send(attachment, user=session.user)
    return attachment.download_url

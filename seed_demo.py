"""Idempotently seed two local conferences. No real users, mail or payments."""
import json
from datetime import datetime
from pathlib import Path

from flask import session
from pytz import timezone
from indico.web.flask.app import make_app
from indico.core.db import db
from indico.core.db.sqlalchemy.protection import ProtectionMode
from indico.core.plugins import plugin_engine
from indico.modules.auth import Identity
from indico.modules.users.operations import create_user, grant_admin
from indico.modules.categories import Category
from indico.modules.categories.operations import create_category
from indico.modules.core.settings import core_settings
from indico.modules.events import Event
from indico.modules.events.models.events import EventType
from indico.modules.events.operations import create_event
from indico.modules.events.layout import layout_settings
from indico.modules.events.layout.models.menu import EventPage, MenuEntry, MenuEntryType
from indico.modules.events.layout.util import menu_entries_for_event

app = make_app()
# Bootstrap switches users within one request, as Indico's shell does.
app.config['REPL'] = True
accounts = json.loads(Path('/tmp/demo-accounts.json').read_text())
tz = timezone('Asia/Shanghai')
specs = [
    ('yujian-ai2027', '遇见科技人工智能学术会议 2027', 'host-a', '#155da0', '上海',
     '围绕人工智能研究与产业应用开展学术交流。此会议及所有资料均为本地演示数据。'),
    ('yujian-energy2027', '遇见科技能源与燃烧学术会议 2027', 'host-b', '#17675b', '长沙',
     '围绕能源转型、清洁燃烧与交叉学科开展交流。此会议及所有资料均为本地演示数据。'),
]
with app.test_request_context(base_url='http://localhost:12880'):
    users = {}
    for item in accounts:
        identity = Identity.query.filter_by(provider='indico', identifier=item['username']).first()
        if identity:
            user = identity.user
        else:
            identity = Identity(provider='indico', identifier=item['username'], password=item['password'])
            user = create_user(item['email'], {'first_name': item['name'], 'last_name': '演示',
                                              'affiliation': '遇见科技'}, identity)
        users[item['username']] = user
    if not users['admin'].is_admin:
        grant_admin(users['admin'])
    session.set_session_user(users['admin'])
    core_settings.set_multi({'site_title': '遇见科技会议服务平台 · 本地演示',
                             'site_organization': '遇见科技'})
    root = Category.get(0)
    category = Category.query.filter_by(title='遇见科技演示会议', is_deleted=False).first()
    if category is None:
        category = create_category(root, {'title': '遇见科技演示会议', 'timezone': 'Asia/Shanghai'})
    # Give demo hosts creation rights without category-wide management access.
    for username in ('host-a', 'host-b'):
        category.update_principal(users[username], add_permissions={'create'})
    db.session.commit()

    for slug, title, username, color, city, intro in specs:
        session.set_session_user(users[username])
        event = Event.query.filter_by(url_shortcut=slug).first()
        new_event = event is None
        if event is None:
            event = create_event(category, EventType.conference, {
                'creator': users[username],
                'title': title, 'url_shortcut': slug, 'description': '<p>' + intro + '</p>',
                'start_dt': tz.localize(datetime(2027, 4, 10, 9)).astimezone(timezone('UTC')),
                'end_dt': tz.localize(datetime(2027, 4, 12, 17)).astimezone(timezone('UTC')),
                'timezone': 'Asia/Shanghai',
            })
        if event.creator != users[username]:
            event.update_principal(event.creator, full_access=False)
            event.creator = users[username]
        event.update_principal(users[username], full_access=True)
        if not event.venue_name:
            event.inherit_location = False
            event.venue_name = city
        layout_settings.set_multi(event, {'use_custom_menu': True,
                                          'header_background_color': color,
                                          'header_text_color': '#ffffff',
                                          'show_social_badges': False})
        db.session.commit()
        # Indico initializes built-in menu items in a separate DB session.
        menu_entries_for_event(event)
        db.session.commit()
        for entry in MenuEntry.query.filter_by(event_id=event.id).all():
            if entry.type == MenuEntryType.internal_link:
                entry.is_enabled = entry.name == 'overview'
                if entry.name == 'overview':
                    entry.title = '首页'
                    entry.position = 0
        page_specs = [
            ('会议委员会', '<h2>会议委员会</h2><p>这里由主办方填写委员会成员与单位。当前为演示内容。</p>'),
            ('会议主题', '<h2>会议主题</h2><p>' + intro + '</p>'),
            ('会议日程', '<h2>会议日程</h2><p>4月10日：报到与开幕；4月11日：专题报告；4月12日：研讨与闭幕。</p>'),
            ('会议地点', '<h2>会议地点</h2><p>' + city + ' · 演示会场，非真实活动地址。</p>'),
            ('重要通知', '<h2>重要通知</h2><p>欢迎访问遇见科技会议演示站。主办方可在后台编辑本页和添加附件。</p>'),
            ('联系我们', '<h2>联系我们</h2><p>这是本地演示，不接收真实参会咨询。</p>'),
        ]
        for position, (page_title, html) in enumerate(page_specs, 1):
            entry = MenuEntry.query.filter_by(event_id=event.id, title=page_title,
                                              type=MenuEntryType.page).first()
            if entry is None:
                page = EventPage(event=event, html=html)
                entry = MenuEntry(event=event, type=MenuEntryType.page,
                                  title=page_title, position=position, page=page)
                db.session.add(entry)
            elif new_event:
                entry.page.html = html
        if new_event:
            event.protection_mode = ProtectionMode.public
            event.visibility = None
            plugin = plugin_engine.get_plugin('yujian_site')
            if plugin:
                plugin.event_settings.set(event, 'published', True)
        db.session.commit()
        print(f'Conference ready: /event/{event.id}/ ({slug})')
    print('Demo seeded. Account secrets remain in the local demo-accounts.json file.')

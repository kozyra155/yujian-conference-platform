"""Create one clearly labelled local complete-template demo; preserve existing demos."""
import io
import json
from pathlib import Path

from indico.web.flask.app import make_app
from indico.core.db import db
from indico.modules.auth import Identity
from indico.modules.events import Event
from indico.modules.events.layout.models.menu import MenuEntry

TITLE = '遇见科技完整建站体验会议（示例）'
app = make_app(config_override={'EMAIL_BACKEND': 'indico.vendor.django_mail.backends.locmem.EmailBackend',
                                'SMTP_USE_CELERY': False})
app.config.update(TESTING=True, REPL=True)
client = app.test_client()
with app.app_context():
    owner = Identity.query.filter_by(provider='indico', identifier='host-a').one().user
    owner_id = owner.id
    existing = Event.query.filter_by(creator_id=owner_id, title=TITLE, is_deleted=False).first()
    existing_id = existing.id if existing else None
if existing_id:
    print(json.dumps({'id': existing_id, 'created': False, 'url': f'http://localhost:12880/event/{existing_id}/'}))
    raise SystemExit(0)
with app.app_context(), client.session_transaction() as session:
    from indico.modules.users import User
    session.set_session_user(User.get(owner_id))
token = json.loads(client.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']
headers = {'X-CSRF-Token': token}
created = client.post('/api/conferences/', json={
    'title': TITLE, 'start': '2027-10-20T09:00', 'end': '2027-10-22T17:00',
    'location': '线上体验 · 示例会议', 'template': 'academic-full',
    'description': '本网站用于体验遇见科技完整会议建站功能，不对应真实会议，不接受真实报名或缴费。'
                   '主办方可以在工作台维护会议横幅、嘉宾介绍、会议动态、重要日期和合作单位，'
                   '也可以编辑会议组织、日程、酒店及历届会议等栏目，预览后再发布。'}, headers=headers)
assert created.status_code == 201, created.status_code
event_id = created.json['id']
try:
    uploaded = client.post(f'/api/conferences/{event_id}/assets',
                           data={'file': (io.BytesIO(Path('/tmp/complete-demo-logo.png').read_bytes()), 'meet-logo.png')},
                           headers=headers)
    assert uploaded.status_code == 201, uploaded.status_code
    image_url = uploaded.json['url']
    payload = client.get(f'/api/conferences/{event_id}/content').json
    content = payload['content']
    content['banner'].update(title='遇见科技 · 完整会议建站体验', title_en='Meet Technology Conference Website Demo',
                             subtitle='从会议筹备到网站发布，让每一项信息井然有序',
                             subtitle_en='Create, edit and publish your conference website')
    content['introduction_en'] = ('This is a demonstration of the Meet Technology conference website builder. '
                                  'It is not a real conference and does not accept registrations or payments. '
                                  'Organizers can maintain speakers, news, dates, partner organizations and website pages.')
    content['speakers'] = [dict(name=f'示例嘉宾 {index}', name_en=f'Example speaker {index}',
                                affiliation='演示资料 · 请替换为实际嘉宾', affiliation_en='Demo content; replace with your speakers',
                                topic=topic, topic_en=topic_en, image='', enabled=True)
                           for index, (topic, topic_en) in enumerate([
                               ('学术交流与创新', 'Research and innovation'), ('科研合作与实践', 'Research collaboration'),
                               ('会议数字化服务', 'Digital conference services'), ('跨学科交流', 'Interdisciplinary exchange')], 1)]
    content['news'] = [dict(title=title, title_en=title_en, date=date, body=body, body_en=body_en, url='', enabled=True)
                       for title, title_en, date, body, body_en in [
                           ('完整会议模板现已开放体验', 'Complete conference template is ready to explore', '2026-10-15',
                            '可在“首页设计”中维护所有首页模块，并在“栏目内容”中编辑完整内页。',
                            'Edit homepage modules in Homepage design and maintain pages in Website sections.'),
                           ('用自己的图片呈现会议特色', 'Make the website your own', '2026-10-14',
                            '横幅、嘉宾照片和单位 Logo 支持上传、替换与移除。所有示例文字均可修改。',
                            'Upload and replace banners, speaker photos and organization logos. All demo text is editable.'),
                           ('报名和投稿由主办方配置', 'Organizers control registration and submissions', '2026-10-13',
                            '平台支持原生报名表和摘要投稿入口，也可以链接到主办方已有服务。此体验会议没有开放报名。',
                            'Use native registration and abstract submissions, or link an external service. Registration is closed for this demo.')]]
    content['dates'] = [dict(label=label, label_en=label_en, date=date, enabled=True)
                        for label, label_en, date in [('早鸟截止（示例）', 'Early deadline (example)', '2027-09-15'),
                                                     ('投稿截止（示例）', 'Submission deadline (example)', '2027-09-30'),
                                                     ('会议日期（示例）', 'Conference dates (example)', '2027-10-20 — 2027-10-22')]]
    for group in content['organizations']:
        group['items'] = [dict(name='遇见科技 · 演示单位', name_en='Meet Technology (demo)', image=image_url, url='', enabled=True)]
    content['contact'].update(name='遇见科技会议服务 · 功能演示', name_en='Meet Technology conference services demo',
                              address='此网站为功能体验，非真实会议报名通知。', address_en='Demonstration only; not an invitation to a real event.')
    content['notices'].update(text='本页面所有嘉宾、日期、合作单位均为演示内容。正式办会时请替换为主办方确认的信息。'
                                   '\n体验站不接受实际报名、投稿或缴费。', text_en='Speakers, dates and organizations are demonstration content. '
                                   'Replace them with confirmed information for your conference.\nNo registrations, submissions or payments are accepted here.')
    content['venue'].update(description='主办方可在这里填写会场地址、会议酒店、交通方式及预订须知。此体验会议不对应实际会场。',
                            description_en='Organizers can provide venue, hotel and travel information here. This demo has no actual venue.')
    saved = client.put(f'/api/conferences/{event_id}/content', json={'revision': payload['revision'],
                       'template': 'academic-full', 'content': content}, headers=headers)
    assert saved.status_code == 200, saved.status_code
    with app.app_context():
        for entry in MenuEntry.query.filter_by(event_id=event_id).all():
            if entry.page:
                entry.page.html = ('<h2>' + entry.title + '</h2><p>本栏目用于体验会议网站编辑。'
                                   '请从网站工作台进入栏目编辑器，填写正式会议信息。</p>'
                                   '<p>这是示例会议，不接受实际报名、投稿或缴费。</p>')
        db.session.commit()
    assert client.post(f'/api/conferences/{event_id}/publication', json={'published': True}, headers=headers).status_code == 200
except Exception:
    with app.app_context():
        db.session.rollback()
        Event.get(event_id).is_deleted = True
        db.session.commit()
    raise
print(json.dumps({'id': event_id, 'created': True, 'url': f'http://localhost:12880/event/{event_id}/',
                  'builder_url': f'http://localhost:12880/conference/{event_id}/'}))

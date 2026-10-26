const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base='http://192.168.2.36:12880';
function python(code){return execFileSync('docker',['compose','-p','yujian-indico-v1','exec','-T','indico-web','/opt/indico/.venv/bin/python','-c',code],{cwd:__dirname,encoding:'utf8'});}
const cleanup=String.raw`
def cleanup_fixture(event_id,user_id):
 with app.test_request_context(base_url='http://192.168.2.36:12880'):
  db.session.rollback()
  if event_id:
   event=Event.get(event_id)
   assert event.id not in (22,61) and event.title.startswith('参会账号界面验收 ')
   event.is_deleted=True
  if user_id:
   user=User.get(user_id)
   assert user.email.startswith('account-ui-owner-') and user.email.endswith('@conference.test')
   user.is_deleted=True
  db.session.commit()
`;
const setup=String.raw`
import atexit,json,re,uuid
from datetime import timedelta
from urllib.parse import urlsplit
from indico.web.flask.app import make_app
from indico.core.db import db
from indico.modules.auth import Identity
from indico.modules.users import User
from indico.modules.users.operations import create_user
from indico.modules.events import Event
from indico.modules.events.layout.models.menu import MenuEntry
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.util import create_personal_data_fields
from indico.util.date_time import now_utc
from indico.vendor import django_mail
app=make_app(config_override={'EMAIL_BACKEND':'indico.vendor.django_mail.backends.locmem.EmailBackend','SMTP_USE_CELERY':False})
app.config.update(TESTING=True,REPL=True)
ready=False
event_id=user_id=None
`+cleanup+String.raw`
def failed_setup():
 if not ready:cleanup_fixture(event_id,user_id)
atexit.register(failed_setup)
with app.test_request_context(base_url='http://192.168.2.36:12880'):
 suffix=uuid.uuid4().hex[:12]
 name='account-ui-owner-'+suffix
 password=uuid.uuid4().hex+'!Q8'
 user=create_user(name+'@conference.test',{'first_name':'参会界面','last_name':'临时主办方'},Identity(provider='indico',identifier=name,password=password))
 db.session.commit()
 user_id=user.id
 owner=app.test_client()
 with owner.session_transaction() as session:session.set_session_user(user)
 token=json.loads(owner.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']
 created=owner.post('/api/conferences/',json={'title':'参会账号界面验收 '+suffix,'start':'2027-10-20T09:00','end':'2027-10-22T17:00','location':'武汉','description':'仅用于访客账号界面验收。','template':'academic-full'},headers={'X-CSRF-Token':token})
 assert created.status_code==201
 event_id=created.json['id']
 event=Event.get(event_id)
 form=RegistrationForm(event=event,title='参会账号报名',currency='CNY',start_dt=now_utc()-timedelta(days=1),end_dt=now_utc()+timedelta(days=2),require_login=True,require_captcha=False,notification_sender_address='no-reply@example.invalid')
 create_personal_data_fields(form)
 db.session.add(form)
 event.cfa.open()
 db.session.commit()
 payload=owner.get(f'/api/conferences/{event_id}/content').json
 for action in ('registration','submission'):payload['content']['actions'][action]['enabled']=True
 assert owner.put(f'/api/conferences/{event_id}/content',json={'revision':payload['revision'],'content':payload['content'],'template':'academic-full'},headers={'X-CSRF-Token':token}).status_code==200
 assert owner.post(f'/api/conferences/{event_id}/publication',json={'published':True},headers={'X-CSRF-Token':token}).status_code==200
 visitor=app.test_client()
 visitor.environ_base['REMOTE_ADDR']='192.0.2.'+str(int(suffix[:2],16)%200+20)
 target=f'/event/{event_id}/registrations/'
 entry=visitor.get(f'/event/{event_id}/register/',query_string={'next':target})
 assert entry.status_code==302
 visitor.get(entry.location)
 assert visitor.get('/api/captcha/generate').status_code==200
 with visitor.session_transaction() as session:answer=session['captcha_state']
 csrf=json.loads(visitor.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']
 email='account-ui-attendee-'+suffix+'@example.com'
 sent=visitor.post(entry.location,data={'email':email,'captcha':answer,'is_email_verification':'','csrf_token':csrf})
 assert sent.status_code==302
 message=next(message for message in django_mail.outbox if email in message.to)
 verification_url=next(url for url in re.findall(r'https?://[^\s<>()]+',message.body) if urlsplit(url).path=='/register/')
 ready=True
 page_id=MenuEntry.query.filter_by(event_id=event_id).filter(MenuEntry.page_id.isnot(None)).order_by(MenuEntry.position).first().page_id
 print(json.dumps({'event_id':event_id,'page_id':page_id,'form_id':form.id,'user_id':user_id,'username':name,'password':password,'verification_url':verification_url}))
`;
(async()=>{
 const browser=await chromium.launch();let fixture;const errors=[];
 try{
  fixture=JSON.parse(python(setup));
  async function context(){const value=await browser.newContext({locale:'zh-CN',viewport:{width:1440,height:1000}});value.setDefaultTimeout(10000);await value.addInitScript(()=>localStorage.setItem('meet-language','zh'));await value.route('**/register/**',route=>route.request().method()==='POST'?route.abort('blockedbyclient'):route.continue());return value;}
  const guest=await context();const page=await guest.newPage();page.on('pageerror',error=>errors.push(error.message));
  async function entryChecks(page,name){
   const strip=page.locator('[data-conference-entry]');await strip.waitFor();
   assert.equal(await strip.locator('[data-conference-login]').isVisible(),true);
   assert.equal(await strip.locator('[data-conference-member]').isVisible(),false);
   assert.equal(new URL(await strip.locator('[data-conference-enroll]').getAttribute('href'),base).searchParams.get('next'),`/event/${fixture.event_id}/registrations/`);
   for(const width of [1440,390,320]){await page.setViewportSize({width,height:1000});await page.mouse.move(0,0);assert.equal(await strip.isVisible(),true);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await strip.screenshot({path:__dirname+`/../output/conference-entry-${name}-${width}.png`});}
  }
  await page.goto(base+`/event/${fixture.event_id}/`);await page.evaluate(()=>window.MeetPortal.refreshSession());
  await entryChecks(page,'complete');
  await page.locator('.language-toggle').click();await page.getByRole('link',{name:'Register for conference',exact:true}).waitFor();await page.locator('.language-toggle').click();
  await page.goto(base+`/event/${fixture.event_id}/page/${fixture.page_id}`);await page.evaluate(()=>window.MeetPortal.refreshSession());await entryChecks(page,'content');
  assert.equal(new URL(await page.locator('[data-conference-login]').getAttribute('href'),base).searchParams.get('next'),`/event/${fixture.event_id}/page/${fixture.page_id}`);
  await page.goto(base+`/event/${fixture.event_id}/`);await page.evaluate(()=>window.MeetPortal.refreshSession());
  const signup=page.locator('[data-guest-signup]');assert.equal(await signup.isVisible(),true);
  const login=page.locator('.header-actions .login-link');assert.equal(new URL(await login.getAttribute('href'),base).searchParams.get('next'),`/event/${fixture.event_id}/`,'Session refresh must preserve conference login target');
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:1000});assert.equal(await signup.isVisible(),true,`Guest signup visible at ${width}`);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);}
  await page.goto(base+`/event/${fixture.event_id}/abstracts/`);await page.locator('.meet-native-business').waitFor();await page.evaluate(()=>window.MeetPortal.refreshSession());
  for(const width of [390,320]){await page.setViewportSize({width,height:1000});assert.equal(await page.locator('[data-guest-signup]').isVisible(),true);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Native guest header must fit ${width}px`);}
  await page.goto(base+`/event/${fixture.event_id}/`);await page.evaluate(()=>window.MeetPortal.refreshSession());
  await page.locator('[data-conference-enroll]').click();
  await page.locator('[data-conference-auth]').waitFor();assert.equal(new URL(page.url()).searchParams.get('next'),`/event/${fixture.event_id}/registrations/`);
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:__dirname+`/../output/conference-login-${width}.png`,fullPage:true});}
  await page.getByRole('link',{name:'创建参会账号',exact:true}).click();await page.locator('#meet-register-email-form input[name=captcha]').waitFor();
  await page.locator('#captcha .ui.message img').waitFor();
  const emailInput=page.locator('#meet-register-email-form input[name=email]');await emailInput.fill('draft@example.com');
  await page.locator('.language-toggle').click();await page.getByRole('link',{name:'Create account',exact:true}).waitFor();assert.equal(await emailInput.inputValue(),'draft@example.com');
  await page.locator('.language-toggle').click();
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.equal(await page.locator('#captcha .ui.message').evaluate(box=>box.querySelector('.ui.buttons').getBoundingClientRect().right<=box.getBoundingClientRect().right+1),true,'CAPTCHA controls must fit inside their card');await page.screenshot({path:__dirname+`/../output/conference-register-${width}.png`,fullPage:true});}
  const fresh=await context();const profile=await fresh.newPage();profile.on('pageerror',error=>errors.push(error.message));await profile.goto(fixture.verification_url);
  await profile.locator('#signup-container input[name=first_name]').waitFor();assert.equal(await profile.locator('[data-conference-auth]').count(),1);
  await profile.locator('#signup-container input[name=first_name]').fill('账号草稿');
  await profile.locator('.language-toggle').click();await profile.getByRole('link',{name:'Create account',exact:true}).waitFor();assert.equal(await profile.locator('#signup-container input[name=first_name]').inputValue(),'账号草稿');
  await profile.locator('.language-toggle').click();
  await profile.mouse.move(0,0);
  for(const width of [1440,390,320]){await profile.setViewportSize({width,height:1000});await profile.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);assert.equal(await profile.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await profile.screenshot({path:__dirname+`/../output/conference-account-profile-${width}.png`,fullPage:true});}
  await page.getByRole('link',{name:'立即登录',exact:true}).click();await page.locator('[name=identifier]').fill(fixture.username);await page.locator('[name=password]').fill(fixture.password);
  await Promise.all([page.waitForURL(url=>url.pathname.startsWith(`/event/${fixture.event_id}/registrations/`)),page.locator('#login-form').evaluate(form=>form.requestSubmit())]);
  assert.equal(new URL(page.url()).pathname,`/event/${fixture.event_id}/registrations/${fixture.form_id}/`);
  await page.goto(base+`/event/${fixture.event_id}/`);await page.evaluate(()=>window.MeetPortal.refreshSession());assert.equal(await page.locator('[data-guest-signup]').isVisible(),false);assert.equal(await page.locator('.account-menu').isVisible(),true);assert.equal(await page.locator('.complete-actions a').filter({hasText:'会议报名'}).getAttribute('href'),`/event/${fixture.event_id}/registrations/`);
  assert.equal(await page.locator('[data-conference-login]').isVisible(),false);assert.equal(await page.locator('[data-conference-member]').isVisible(),true);assert.equal(await page.locator('[data-conference-enroll]').getAttribute('href'),`/event/${fixture.event_id}/registrations/`);
  python(`from indico.web.flask.app import make_app\nfrom indico.core.db import db\nfrom indico.modules.events import Event\nfrom yujian_site import YujianSitePlugin\nfrom yujian_site.site_content import get_site_content\napp=make_app()\nwith app.app_context():\n event=Event.get(${fixture.event_id})\n assert event.title.startswith('参会账号界面验收 ') and event.id not in (22,61)\n content=get_site_content(event)\n content['theme']={'layout':'simple-2','accent':'#3f67c8'}\n YujianSitePlugin.event_settings.set(event,'content',content)\n db.session.commit()`);
  const vertical=await (await context()).newPage();vertical.on('pageerror',error=>errors.push(error.message));await vertical.goto(base+`/event/${fixture.event_id}/`);await vertical.evaluate(()=>window.MeetPortal.refreshSession());await entryChecks(vertical,'vertical');
  python(`from indico.web.flask.app import make_app\nfrom indico.core.db import db\nfrom indico.modules.events import Event\nfrom yujian_site import YujianSitePlugin\napp=make_app(config_override={'EMAIL_BACKEND':'indico.vendor.django_mail.backends.locmem.EmailBackend','SMTP_USE_CELERY':False})\nwith app.app_context():\n event=Event.get(${fixture.event_id})\n assert event.title.startswith('参会账号界面验收 ') and event.id not in (22,61)\n YujianSitePlugin.event_settings.set(event,'template','academic')\n db.session.commit()`);
  const legacy=await (await context()).newPage();legacy.on('pageerror',error=>errors.push(error.message));await legacy.goto(base+`/event/${fixture.event_id}/`);await legacy.evaluate(()=>window.MeetPortal.refreshSession());
  await entryChecks(legacy,'legacy');
  for(const width of [1440,390,320]){await legacy.setViewportSize({width,height:1000});assert.equal(await legacy.locator('[data-guest-signup]').isVisible(),true);assert.equal(await legacy.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Legacy guest header must fit ${width}px`);}
  python(`from indico.web.flask.app import make_app\nfrom indico.core.db import db\nfrom indico.modules.events import Event\nfrom indico.modules.events.registration.models.forms import RegistrationForm\nfrom indico.util.date_time import now_utc\nfrom datetime import timedelta\napp=make_app()\nwith app.app_context():\n event=Event.get(${fixture.event_id})\n assert event.title.startswith('参会账号界面验收 ') and event.id not in (22,61)\n form=RegistrationForm.get(${fixture.form_id})\n form.end_dt=now_utc()-timedelta(minutes=1)\n db.session.commit()`);
  await legacy.reload();await legacy.evaluate(()=>window.MeetPortal.refreshSession());assert.equal(await legacy.locator('[data-conference-entry] [aria-disabled=true]').isVisible(),true);assert.equal(await legacy.locator('[data-conference-enroll]').count(),0);assert.equal(await legacy.locator('[data-conference-login]').isVisible(),true);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,conference_return:true,guest_signup_mobile:true,native_and_legacy_guest_headers:true,banner_registration_login:true,content_page_return:true,vertical_layout_entries:true,closed_registration_disabled:true,email_captcha_preserved:true,new_browser_profile_context:true,bilingual_draft_preserved:true,real_login_return:true,logged_in_signup_hidden:true,responsive:[320,390,1440],browser_errors:errors,external_registration_email_sent:false}));
 }finally{
  await browser.close();
  if(fixture)python(`from indico.web.flask.app import make_app\nfrom indico.core.db import db\nfrom indico.modules.users import User\nfrom indico.modules.events import Event\napp=make_app(config_override={'EMAIL_BACKEND':'indico.vendor.django_mail.backends.locmem.EmailBackend','SMTP_USE_CELERY':False})\n${cleanup}\ncleanup_fixture(${fixture.event_id},${fixture.user_id})`);
 }
})().catch(error=>{console.error(error.stack);process.exitCode=1});

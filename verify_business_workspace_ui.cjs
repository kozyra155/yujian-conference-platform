const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base='http://192.168.2.36:12880';
function python(code){return execFileSync('docker',['compose','-p','yujian-indico-v1','exec','-T','indico-web','/opt/indico/.venv/bin/python','-c',code],{cwd:__dirname,encoding:'utf8'});}
async function login(page,account){await page.goto(base+'/login/');await page.locator('[name=identifier]').fill(account.username);await page.locator('[name=password]').fill(account.password);await Promise.all([page.waitForURL(u=>!u.pathname.startsWith('/login/')),page.locator('#login-form').evaluate(f=>f.requestSubmit())]);}
const setup=String.raw`
import atexit,json,os,uuid
os.environ['PYTEST_CURRENT_TEST']='verify_business_workspace_ui'
from datetime import timedelta
from indico.web.flask.app import make_app
from indico.modules.users.operations import create_user
from indico.modules.auth import Identity
from indico.modules.events import Event
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.util import create_personal_data_fields
from indico.core.db import db
from indico.util.date_time import now_utc
app=make_app(config_override={'EMAIL_BACKEND':'indico.vendor.django_mail.backends.locmem.EmailBackend','SMTP_USE_CELERY':False})
app.config.update(TESTING=True,REPL=True)
fixture_ready=False
user_id=event_id=None
def cleanup_failed_setup():
 if fixture_ready or user_id is None:return
 with app.app_context():
  from indico.modules.users import User
  user=User.get(user_id)
  assert user.email.startswith('business-ui-') and user.email.endswith('@conference.test')
  if event_id is not None:
   event=Event.get(event_id)
   assert event.creator_id==user.id and event.id not in (22,61)
   event.is_deleted=True
  user.is_deleted=True
  db.session.commit()
atexit.register(cleanup_failed_setup)
with app.test_request_context(base_url='http://192.168.2.36:12880'):
 username='business-ui-'+uuid.uuid4().hex[:12]
 password=uuid.uuid4().hex+'!A8'
 user=create_user(username+'@conference.test',{'first_name':'业务验收','last_name':'临时账号'},Identity(provider='indico',identifier=username,password=password))
 db.session.commit()
 user_id=user.id
 account={'id':user.id,'username':username,'password':password}
 client=app.test_client()
 with client.session_transaction() as session:session.set_session_user(user)
 token=json.loads(client.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']
 created=client.post('/api/conferences/',json={'title':'业务工作台验收 '+username,'start':'2027-10-20T09:00','end':'2027-10-22T17:00','location':'武汉','description':'临时业务验收会议。','template':'academic-full'},headers={'X-CSRF-Token':token})
 assert created.status_code==201
 event_id=created.json['id']
 event=Event.get(event_id)
 form=RegistrationForm(event=event,title='参会报名验收',currency='CNY',start_dt=now_utc()-timedelta(days=1),end_dt=now_utc()+timedelta(days=2),require_login=True,require_captcha=False,notification_sender_address='no-reply@example.invalid')
 create_personal_data_fields(form)
 db.session.add(form)
 event.cfa.open()
 db.session.commit()
 form_id=form.id
 response=client.post(f'/event/{event_id}/registrations/{form_id}/',json={'first_name':'业务验收','last_name':'临时账号','email':user.email,'affiliation':'遇见科技'},headers={'X-CSRF-Token':token})
 assert response.status_code==200 and 'redirect' in response.json
 author={'first_name':'业务验收','last_name':'临时账号','email':user.email,'affiliation':'遇见科技','roles':['primary','speaker']}
 response=client.post(f'/event/{event_id}/abstracts/submit',data={'title':'业务工作台投稿验收','description':'真实原生摘要。','person_links':json.dumps([author]),'csrf_token':token},headers={'X-CSRF-Token':token,'X-Requested-With':'XMLHttpRequest'})
 assert response.status_code==200 and 'redirect' in response.json
 fixture_ready=True
 print(json.dumps({'account':account,'event_id':event_id,'form_id':form_id}))
`;
(async()=>{
 const browser=await chromium.launch();let fixture;const result={};
 try{
  fixture=JSON.parse(python(setup));
  const context=await browser.newContext({locale:'zh-CN',viewport:{width:1440,height:1000}});context.setDefaultTimeout(10000);await context.addInitScript(()=>localStorage.setItem('meet-language','zh'));
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));await login(page,fixture.account);
  await page.goto(base+'/participation/');
  assert.equal(await page.locator('[data-test=business-workspace]').count(),1,'Participant route must mount the business workspace');
  const workspace=page.locator('[data-test=business-workspace]');await workspace.locator('[data-test=business-ready]').waitFor();
  await page.getByRole('tab',{name:/我的报名/}).click();assert.equal(await workspace.locator('[data-test=participation-record]').count(),1);
  await workspace.getByRole('link',{name:'报名详情',exact:true}).waitFor();assert.match(await workspace.innerText(),/武汉/);
  const search=workspace.getByRole('textbox',{name:'搜索业务记录',exact:true});await search.fill('不存在的会议');await workspace.getByText('没有匹配的记录',{exact:true}).waitFor();await search.fill('');
  await workspace.locator('.el-select').click();await page.getByRole('option',{name:'报名成功',exact:true}).click();assert.equal(await workspace.locator('[data-test=participation-record]').count(),1,'Own status filter preserves matching records');
  await page.getByRole('tab',{name:/我的稿件/}).click();await workspace.getByText('业务工作台投稿验收',{exact:true}).waitFor();
  const detail=workspace.getByRole('link',{name:'稿件详情',exact:true});assert.equal((await page.request.get(base+await detail.getAttribute('href'))).status(),200);
  await page.getByRole('tab',{name:/审稿任务/}).click();await workspace.getByText('暂无审稿任务',{exact:true}).waitFor();
  await page.getByRole('tab',{name:/我的报名/}).click();
  assert.equal(await workspace.locator('.business-stats article>.el-icon').first().evaluate(el=>el.getBoundingClientRect().width>=40),true,'Statistic icons must have room for their SVG');
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Participation overflow at ${width}`);await page.screenshot({path:__dirname+`/../output/business-participation-${width}.png`,fullPage:true,animations:'disabled'});}
  await page.locator('.language-toggle').click();await page.getByRole('tab',{name:/My registrations/}).click();await workspace.getByText('Registered',{exact:true}).waitFor();
  await page.locator('.language-toggle').click();
  await page.goto(base+`/conference/${fixture.event_id}/operations/`);await workspace.locator('[data-test=business-ready]').waitFor();
  assert.equal(await workspace.locator('[data-test=registration-form]').count(),1);await workspace.getByText('参会报名验收',{exact:true}).waitFor();
  const list=workspace.getByRole('link',{name:'名单与导出',exact:true});assert.equal((await page.request.get(base+await list.getAttribute('href'))).status(),200);
  await page.getByRole('tab',{name:'投稿与审稿',exact:true}).click();await workspace.getByText('业务工作台投稿验收',{exact:true}).waitFor();
  assert.equal(await workspace.getByRole('link',{name:'全部稿件',exact:true}).evaluate(el=>{const s=getComputedStyle(el);return s.color!==s.backgroundColor;}),true,'Primary link text must be visible against its background');
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Operations overflow at ${width}`);await page.screenshot({path:__dirname+`/../output/business-operations-${width}.png`,fullPage:true,animations:'disabled'});}
  await page.route(`**/api/conferences/${fixture.event_id}/operations`,route=>route.fulfill({status:503,json:{}}));await workspace.getByRole('button',{name:'刷新',exact:true}).click();await workspace.locator('[data-test=business-error]').waitFor();await page.unroute(`**/api/conferences/${fixture.event_id}/operations`);await workspace.getByRole('button',{name:'重试',exact:true}).click();await workspace.locator('[data-test=business-ready]').waitFor();
  const actual=await(await page.request.get(base+`/api/conferences/${fixture.event_id}/operations`)).json();
  await page.route(`**/api/conferences/${fixture.event_id}/operations`,route=>route.fulfill({json:{...actual,features:{registration:false,abstracts:false},registration:{enabled:false,total:0,pending:0,forms:[],links:{}},submission:{enabled:false,total:0,pending:0,recent:[],links:{}}}}));await workspace.getByRole('button',{name:'刷新',exact:true}).click();await workspace.locator('[data-test=business-ready]').waitFor();await workspace.getByText('尚未启用投稿功能',{exact:true}).waitFor();assert.equal(await workspace.getByRole('link',{name:'全部稿件',exact:true}).count(),0);assert.equal(await workspace.getByRole('link',{name:'打开功能配置',exact:true}).getAttribute('href'),actual.event.feature_url);await page.unroute(`**/api/conferences/${fixture.event_id}/operations`);
  assert.deepEqual(errors,[]);Object.assign(result,{passed:true,real_registration:true,real_submission:true,personal_search:true,status_filter:true,review_empty:true,canonical_native_links:true,bilingual_states:true,error_retry:true,disabled_feature:true,responsive:[320,390,1440],browser_errors:errors});
 }finally{
  await browser.close();if(fixture)python(`from indico.web.flask.app import make_app\nfrom indico.modules.users import User\nfrom indico.modules.events import Event\nfrom indico.core.db import db\napp=make_app()\nwith app.app_context():\n user=User.get(${fixture.account.id})\n assert user.email.startswith('business-ui-') and user.email.endswith('@conference.test')\n event=Event.get(${fixture.event_id})\n assert event.creator_id==user.id and event.title.startswith('业务工作台验收 ') and event.id not in (22,61)\n event.is_deleted=True\n user.is_deleted=True\n db.session.commit()`);
 }
 fs.writeFileSync(__dirname+'/../output/business-workspace-ui.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
})().catch(e=>{console.error(e.message);process.exit(1)});

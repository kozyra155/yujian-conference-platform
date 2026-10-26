// Run after web restart. Submissions are covered by the memory-mail integration test.
const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const {execFileSync}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const setup=`import json,uuid
from indico.web.flask.app import make_app
from indico.core.config import config
from indico.core.db import db
from indico.modules.users import User
from indico.modules.users.operations import create_user
from indico.modules.auth import Identity
from indico.modules.events import Event
app=make_app(config_override={'EMAIL_BACKEND':'indico.vendor.django_mail.backends.locmem.EmailBackend','SMTP_USE_CELERY':False})
app.config.update(REPL=True,TESTING=True)
`;
function python(code){return execFileSync('docker',['compose','-p','yujian-indico-v1','exec','-T','indico-web','/opt/indico/.venv/bin/python','-c',setup+code],{cwd:__dirname,encoding:'utf8',maxBuffer:1024*1024});}
(async()=>{
 let fixture,browser;
 const errors=[];
 try{
  fixture=JSON.parse(python(`with app.test_request_context():
 name='intent-ui-'+uuid.uuid4().hex
 user=create_user(name+'@example.invalid',{'first_name':'Intent UI','last_name':'fixture'},Identity(provider='indico',identifier=name,password=uuid.uuid4().hex))
 db.session.commit()
 user_id=user.id
 base=config.BASE_URL
try:
 client=app.test_client()
 with app.app_context(),client.session_transaction() as session:
  session.set_session_user(User.get(user_id))
 csrf=json.loads(client.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']
 created=client.post('/api/conferences/',json={'title':'意向界面验收 '+name,'start':'2027-11-20T09:00','end':'2027-11-22T17:00','location':'武汉','description':'隔离界面验收','template':'academic-full'},headers={'X-CSRF-Token':csrf})
 assert created.status_code==201
 event_id=created.json['id']
 payload=client.get(f'/api/conferences/{event_id}/content').json
 payload['content']['matchmaking'].update(enabled=True,text='欢迎登记技术、需求与投资合作意向。',text_en='Share your technology, business needs or investment interests.')
 for section in payload['content']['sections']:
  if section['key']=='matchmaking': section['enabled']=True
 saved=client.put(f'/api/conferences/{event_id}/content',json={'revision':payload['revision'],'template':payload['template'],'content':payload['content']},headers={'X-CSRF-Token':csrf})
 assert saved.status_code==200
 assert client.post(f'/api/conferences/{event_id}/publication',json={'published':True},headers={'X-CSRF-Token':csrf}).status_code==200
 with app.test_request_context(base_url=base): cookie_name=app.session_cookie_name
 cookie=next(cookie for cookie in client._cookies.values() if cookie.key==cookie_name)
 print(json.dumps({'base':base,'event_id':event_id,'user_id':user_id,'cookie_name':cookie.key,'cookie_value':cookie.value}))
except BaseException:
 with app.app_context():
  for event in Event.query.filter_by(creator_id=user_id,is_deleted=False):
   assert event.title.startswith('意向界面验收 ')
   event.is_deleted=True
  User.get(user_id).is_deleted=True
  db.session.commit()
 raise`));
  browser=await chromium.launch({headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'zh-CN'});
  await context.addInitScript(()=>localStorage.setItem('meet-language','zh'));
  const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
  page.setDefaultTimeout(15000);
  const interest=fixture.base+`/event/${fixture.event_id}/interest/`;
  await page.goto(fixture.base+`/event/${fixture.event_id}/`);
  assert.equal(await page.locator(`a[href="/event/${fixture.event_id}/interest/"]`).count()>0,true);
  await page.goto(interest);
  await page.locator('.interest-options article').first().waitFor();
  assert.equal(await page.locator('.interest-options article').count(),3);
  assert.match(await page.locator('aside').innerText(),/请先登录/);
  assert.match(await page.locator('aside a').last().getAttribute('href'),/interest/);
  const links=await page.locator('.interest-action').evaluateAll(elements=>elements.map(element=>element.href));
  assert.equal(links.length,3);
  const out=path.resolve(__dirname,'../output');fs.mkdirSync(out,{recursive:true});
  for(const width of [1440,390,320]){
   await page.setViewportSize({width,height:1000});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`overflow at ${width}`);
   await page.screenshot({path:path.join(out,`interest-${width}.png`),fullPage:true});
  }
  await page.locator('.language-toggle').click();
  await page.waitForFunction(()=>document.documentElement.lang==='en');
  assert.match(await page.locator('h1').innerText(),/Register your interest/);
  await context.addCookies([{name:fixture.cookie_name,value:fixture.cookie_value,url:fixture.base,httpOnly:true,sameSite:'Lax'}]);
  for(const href of links){
   await page.goto(href);
   await page.getByText('是否计划参会 / Attendance plan',{exact:true}).waitFor();
   const text=await page.locator('body').innerText();
   assert.match(text,/单位 \/ Organization/);assert.match(text,/联系方式 \/ Phone/);
  }
  assert.deepEqual(errors,[]);
  const result={passed:true,landing_choices:3,native_forms_rendered:3,bilingual:true,widths:[1440,390,320],browser_errors:errors};
  fs.writeFileSync(path.join(out,'interest-ui.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
 }finally{
  if(browser)await browser.close();
  if(fixture)python(`with app.app_context():
 event=Event.get(${fixture.event_id})
 assert event.title.startswith('意向界面验收 ')
 event.is_deleted=True
 user=User.get(${fixture.user_id})
 assert user.email.startswith('intent-ui-') and user.email.endswith('@example.invalid')
 user.is_deleted=True
 db.session.commit()`);
 }
})().catch(error=>{console.error(error.message);process.exit(1)});

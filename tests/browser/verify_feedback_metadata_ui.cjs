const projectRoot=require('node:path').resolve(__dirname,'../..');
// Run after the combined frontend build and web restart. Uses only a disposable user and conference.
const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const dockerArgs=['compose','-p','yujian-indico-v1','exec','-T','indico-web','/opt/indico/.venv/bin/python','-c'];
const appCode=`from indico.web.flask.app import make_app
from indico.core.config import config
from indico.core.db import db
from indico.modules.auth import Identity
from indico.modules.events import Event
from indico.modules.users import User
from indico.modules.users.operations import create_user
import json,uuid
app=make_app(config_override={'EMAIL_BACKEND':'indico.vendor.django_mail.backends.locmem.EmailBackend','SMTP_USE_CELERY':False})
app.config.update(REPL=True,TESTING=True)
`;
function python(code){return execFileSync('docker',[...dockerArgs,appCode+code],{cwd:projectRoot,encoding:'utf8',maxBuffer:1024*1024});}
(async()=>{
 let browser,fixture,eventId;
 const errors=[],title=`会议资料界面验收 ${Date.now()}`;
 try{
  fixture=JSON.parse(python(`with app.test_request_context():
 name='metadata-ui-'+uuid.uuid4().hex
 user=create_user(name+'@example.invalid',{'first_name':'Metadata UI','last_name':'fixture'},Identity(provider='indico',identifier=name,password=uuid.uuid4().hex))
 db.session.commit()
 user_id=user.id
 base=config.BASE_URL
try:
 client=app.test_client()
 with app.app_context(),client.session_transaction() as session:
  session.set_session_user(User.get(user_id))
 client.get('/assets/js-vars/user.js?portal=1')
 with app.test_request_context(base_url=base):
  cookie_name=app.session_cookie_name
 cookie=next(cookie for cookie in client._cookies.values() if cookie.key==cookie_name)
 print(json.dumps({'base':base,'user_id':user_id,'cookie_name':cookie.key,'cookie_value':cookie.value}))
except BaseException:
 with app.app_context():
  User.get(user_id).is_deleted=True
  db.session.commit()
 raise`));
  browser=await chromium.launch({headless:true});
  const context=await browser.newContext({locale:'zh-CN',viewport:{width:1440,height:1050}});
  await context.addCookies([{name:fixture.cookie_name,value:fixture.cookie_value,url:fixture.base,httpOnly:true,sameSite:'Lax'}]);
  await context.addInitScript(()=>localStorage.setItem('meet-language','zh'));
  const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
  page.setDefaultTimeout(15000);
  await page.goto(fixture.base+'/conference/create/');
  await page.locator('[data-workspace-ready]').waitFor();
  await page.locator('#builder-form button[type=submit]').click();
  await page.waitForFunction(()=>document.querySelectorAll('.el-form-item__error').length>=6);
  assert.ok(await page.locator('.el-form-item__error').count()>=6,'Missing required basic fields are identified');
  const form=page.locator('#builder-form');
  await form.locator('[name=title]').fill(title);
  for(const [name,value] of [['start','2030-06-10 09:00'],['end','2030-06-12 17:00']]){
   await form.locator(`[name=${name}]`).fill(value);await form.locator(`[name=${name}]`).press('Tab');
  }
  await form.locator('[name=organizer_name]').fill('界面验收临时主办单位');
  await form.locator('[name=organizer_phone]').fill('010-12345678');
  async function select(scope,name,value){const input=scope.locator(`input[name=${name}]`);await input.fill(value);await page.getByRole('option',{name:value,exact:true}).click();await input.press('Escape');}
  await select(form,'province','湖北省');await select(form,'city','武汉市');
  await form.locator('[name=detail_address]').fill('待定');
  await select(form,'subject_domains','数学');await select(form,'subject_domains','人工智能');
  await select(form,'planned_indexing','SCI');await select(form,'planned_indexing','EI');
  await form.locator('.el-tag').filter({hasText:'SCI'}).locator('.el-tag__close').click();
  await form.locator('textarea[name=description]').fill('界面验收专用简介，测试结束后清理。');
  const posted=page.waitForResponse(response=>response.url()===fixture.base+'/api/conferences/'&&response.request().method()==='POST');
  await form.locator('button[type=submit]').click();
  const response=await posted;assert.equal(response.status(),201);
  await page.waitForURL(/\/conference\/\d+\/$/);eventId=Number(new URL(page.url()).pathname.split('/')[2]);await page.locator('[data-workspace-ready]').waitFor();
  let payload=await(await page.request.get(fixture.base+`/api/conferences/${eventId}/basic`)).json();
  assert.deepEqual(payload.basic.subject_domains,['数学','人工智能']);assert.deepEqual(payload.basic.planned_indexing,['EI']);
  assert.equal(payload.basic.city,'武汉市');assert.equal(payload.basic.detail_address,'待定');
  await page.getByRole('tab',{name:'站点设置',exact:true}).click();
  const basic=page.locator('#conference-basic');await basic.locator('textarea[name=description]').waitFor();
  await basic.locator('[name=title]').fill(title+' 已更新');
  await basic.locator('[name=organizer_phone]').fill('027-87654321');
  await basic.locator('textarea[name=description]').fill('已修改简介正文。');
  const saved=page.waitForResponse(result=>result.url().endsWith(`/api/conferences/${eventId}/basic`)&&result.request().method()==='PUT');
  await basic.getByRole('button',{name:'保存基本信息',exact:true}).click();assert.equal((await saved).status(),200);
  payload=await(await page.request.get(fixture.base+`/api/conferences/${eventId}/basic`)).json();
  assert.equal(payload.basic.title,title+' 已更新');assert.equal(payload.basic.organizer_phone,'027-87654321');assert.equal(payload.basic.description,'已修改简介正文。');
  await basic.locator('[name=title]').fill(title+' 未保存草稿');
  python(`from indico.modules.events.operations import update_event
with app.test_request_context():
 event=Event.get(${eventId})
 assert event.creator_id==${fixture.user_id}
 update_event(event,title=event.title+' 原生编辑',description='<p>原生编辑器保存的新简介</p>')
 db.session.commit()`);
  const conflicted=page.waitForResponse(result=>result.url().endsWith(`/api/conferences/${eventId}/basic`)&&result.request().method()==='PUT');
  await basic.getByRole('button',{name:'保存基本信息',exact:true}).click();assert.equal((await conflicted).status(),409);
  assert.equal(await basic.locator('[name=title]').inputValue(),title+' 未保存草稿','Keep the user draft after a native edit conflict');
  payload=await(await page.request.get(fixture.base+`/api/conferences/${eventId}/basic`)).json();
  assert.equal(payload.basic.title,title+' 已更新 原生编辑');assert.equal(payload.basic.description,'原生编辑器保存的新简介');
  await basic.getByRole('button',{name:'重新载入',exact:true}).click();
  await page.locator('.el-message-box').getByRole('button',{name:'重新载入',exact:true}).click();
  await basic.locator('[name=title]').waitFor();
  await page.waitForFunction(expected=>document.querySelector('#conference-basic input[name=title]')?.value===expected,title+' 已更新 原生编辑');
  await page.getByRole('tab',{name:'设为栏目的内容',exact:true}).click();
  assert.deepEqual(await page.locator('.section-guide-grid h3').allTextContents(),['会议日程','注册缴费','场地与交通','酒店介绍','联系我们','其他']);
  await page.getByRole('tab',{name:'站点设置',exact:true}).click();
  for(const width of [390,760,1440]){await page.setViewportSize({width,height:1050});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`No horizontal overflow at ${width}px`);}
  await page.setViewportSize({width:1440,height:1050});
  await page.screenshot({path:path.join(projectRoot,'../output/feedback-1016/conference-basics-fixed.png'),fullPage:true});
  await page.evaluate(()=>{window.dispatchEvent(new CustomEvent('meet-language-change',{detail:{language:'en'}}));});
  assert.equal(await basic.getByRole('button',{name:'Save conference details',exact:true}).isVisible(),true);
  assert.deepEqual(errors,[]);
  const result={passed:true,required_field_errors:true,multiselect_remove:true,province_city:true,create_and_edit:true,native_edit_conflict_retains_draft:true,section_cards:true,mobile_no_overflow:true,english_labels:true,browser_errors:errors,external_mail_sent:false};
  fs.writeFileSync(path.join(projectRoot,'../output/feedback-1016/metadata-ui-result.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
 }finally{
  if(browser)await browser.close();
  if(fixture){assert.ok(Number.isInteger(fixture.user_id));assert.ok(eventId===undefined||Number.isInteger(eventId));python(`with app.test_request_context():
 user=User.get(${fixture?.user_id})
 assert user is not None and user.email.startswith('metadata-ui-')
 for event in Event.query.filter_by(creator_id=user.id,is_deleted=False).all():
  assert event.title.startswith('会议资料界面验收 ')
  event.is_deleted=True
 user.is_deleted=True
 db.session.commit()`);}
 }
})().catch(error=>{console.error(error);process.exit(1);});

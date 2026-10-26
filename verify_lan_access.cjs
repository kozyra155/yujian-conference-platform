const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');
const base='http://192.168.2.36:12880';
function python(code){return execFileSync('docker',['compose','-p','yujian-indico-v1','exec','-T','indico-web','/opt/indico/.venv/bin/python','-c',code],{cwd:__dirname,encoding:'utf8'});}
const setup=String.raw`
import json,uuid
from indico.web.flask.app import make_app
from indico.core.config import config
from indico.core.db import db
from indico.modules.auth import Identity
from indico.modules.users.operations import create_user
app=make_app(config_override={'EMAIL_BACKEND':'indico.vendor.django_mail.backends.locmem.EmailBackend','SMTP_USE_CELERY':False})
with app.test_request_context(base_url='http://192.168.2.36:12880'):
 assert config.BASE_URL=='http://192.168.2.36:12880'
 name='lan-access-'+uuid.uuid4().hex[:12]
 password=uuid.uuid4().hex+'!A8'
 user=create_user(name+'@conference.test',{'first_name':'内网验收','last_name':'临时账号'},Identity(provider='indico',identifier=name,password=password))
 db.session.commit()
 print(json.dumps({'id':user.id,'username':name,'password':password}))
`;
(async()=>{
 const browser=await chromium.launch();let fixture;
 try{
  fixture=JSON.parse(python(setup));
  const page=await browser.newPage({locale:'zh-CN'});const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto('http://localhost:12880/login/');
  assert.equal(new URL(page.url()).origin,base,'Local bookmarks must redirect to the canonical LAN origin');
  await page.locator('[name=identifier]').fill(fixture.username);
  await page.locator('[name=password]').fill(fixture.password);
  await Promise.all([page.waitForURL(url=>!url.pathname.startsWith('/login/')),page.locator('#login-form').evaluate(form=>form.requestSubmit())]);
  const session=await(await page.request.get(base+'/assets/js-vars/user.js?portal=1')).json();
  assert.equal(session.user.id,fixture.id,'Login must establish a session on the LAN origin');
  for(const path of ['/participation/','/organizer/','/conference/create/','/user/profile/']){
   assert.equal((await page.goto(base+path)).status(),200,path);
   assert.equal(new URL(page.url()).origin,base);
   if(path==='/participation/')await page.locator('[data-test=business-ready]').waitFor();
   if(path==='/user/profile/')await page.locator('#personal-details-form-container input').first().waitFor();
   assert.equal(await page.locator('a[href^="http://localhost:12880"]').count(),0,'Generated links must use the LAN origin');
  }
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,base,local_redirect:true,real_login:true,participant_workspace:true,organizer_workspace:true,create_page:true,profile_form:true,browser_errors:errors}));
 }finally{
  await browser.close();
  if(fixture)python(`from indico.web.flask.app import make_app\nfrom indico.core.db import db\nfrom indico.modules.users import User\napp=make_app(config_override={'EMAIL_BACKEND':'indico.vendor.django_mail.backends.locmem.EmailBackend','SMTP_USE_CELERY':False})\nwith app.app_context():\n user=User.get(${fixture.id})\n assert user.email.startswith('lan-access-') and user.email.endswith('@conference.test')\n user.is_deleted=True\n db.session.commit()`);
 }
})().catch(error=>{console.error(error.message);process.exitCode=1});

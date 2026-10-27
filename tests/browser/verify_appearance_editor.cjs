const projectRoot=require('node:path').resolve(__dirname,'../..');
const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base='http://192.168.2.36:12880';
function python(code){return execFileSync('docker',['compose','-p','yujian-indico-v1','exec','-T','indico-web','/opt/indico/.venv/bin/python','-c',code],{cwd:projectRoot,encoding:'utf8'});}
async function login(page,account){await page.goto(base+'/login/');await page.locator('[name=identifier]').fill(account.username);await page.locator('[name=password]').fill(account.password);await Promise.all([page.waitForURL(u=>!u.pathname.startsWith('/login/')),page.locator('#login-form').evaluate(f=>f.requestSubmit())]);}
(async()=>{
 const browser=await chromium.launch();let fixture,eventId;const result={};
 try{
  fixture=JSON.parse(python("import json,uuid\nfrom indico.web.flask.app import make_app\nfrom indico.modules.users.operations import create_user\nfrom indico.modules.auth import Identity\nfrom indico.core.db import db\napp=make_app(config_override={'EMAIL_BACKEND':'indico.vendor.django_mail.backends.locmem.EmailBackend','SMTP_USE_CELERY':False})\nwith app.test_request_context(base_url='http://192.168.2.36:12880'):\n username='appearance-ui-'+uuid.uuid4().hex[:12]\n password=uuid.uuid4().hex+'!A8'\n user=create_user(username+'@example.invalid',{'first_name':'外观验收','last_name':'临时账号'},Identity(provider='indico',identifier=username,password=password))\n db.session.commit()\n print(json.dumps({'id':user.id,'username':username,'password':password}))"));
  const context=await browser.newContext({locale:'zh-CN',viewport:{width:1440,height:1100}});context.setDefaultTimeout(10000);await context.addInitScript(()=>localStorage.setItem('meet-language','zh'));
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',dialog=>dialog.accept());await login(page,fixture);
  const session=await(await page.request.get(base+'/assets/js-vars/user.js?portal=1')).json();
  const created=await page.request.post(base+'/api/conferences/',{headers:{'X-CSRF-Token':session.csrf_token},data:{title:'外观编辑验收 '+Date.now(),start:'2027-10-20T09:00',end:'2027-10-21T17:00',location:'武汉',description:'自动化临时会议。',template:'academic'}});assert.equal(created.status(),201);const conference=await created.json();eventId=conference.id;
  await page.goto(base+conference.builder_url);await page.locator('[data-workspace-ready]').waitFor();await page.getByRole('tab',{name:'首页设计',exact:true}).click();await page.locator('[data-test=site-editor][data-ready=true]').waitFor();
  assert.equal(await page.locator('[data-test=appearance-picker] input[type=radio]').count(),12,'Appearance gallery must expose twelve presets');
  assert.equal(await page.locator('[data-test=appearance-group]').count(),2);
  const before=await(await page.request.get(base+`/api/conferences/${eventId}/content`)).json();
  const blue=page.locator('[data-test=appearance-simple-2-blue]');await blue.check();assert.equal(await blue.isChecked(),true);await page.getByText('已切换为完整学术模板；保存后应用外观。',{exact:true}).waitFor();
  assert.equal((await(await page.request.get(base+`/api/conferences/${eventId}/content`)).json()).revision,before.revision);
  await page.locator('[data-test=banner-title] input').fill('尚未保存的外观草稿');
  await page.locator('[data-test=preview-appearance]').click();const frame=page.frameLocator('[data-test=appearance-preview-frame]');await frame.locator('.appearance-simple-2').waitFor();
  assert.equal(await frame.getByText('尚未保存的外观草稿',{exact:true}).count(),0,'Preview must use stored content');
  assert.equal(await frame.locator('body').evaluate(body=>getComputedStyle(body).getPropertyValue('--complete-accent').trim()),'#3f67c8','Preview must use chosen accent');
  assert.equal(await page.locator('[data-test=appearance-preview-frame]').getAttribute('sandbox'),'allow-scripts allow-same-origin');
  const frameUrl=await frame.locator('body').evaluate(()=>location.href);await frame.locator('nav a[href]').first().click();assert.equal(await frame.locator('body').evaluate(()=>location.href),frameUrl,'Preview links must not navigate');
  await page.locator('[data-test=appearance-preview-frame]').screenshot({path:projectRoot+'/../output/appearance-preview-simple-2-desktop.png'});
  await page.getByRole('button',{name:'手机视图',exact:true}).click();assert.equal(await page.locator('[data-test=appearance-preview-frame]').evaluate(el=>el.clientWidth),390);
  await page.locator('[data-test=appearance-preview-frame]').screenshot({path:projectRoot+'/../output/appearance-preview-simple-2-mobile.png'});
  const previewStored=await(await page.request.get(base+`/api/conferences/${eventId}/content`)).json();assert.deepEqual(previewStored,before,'Preview cannot save template, revision or content');
  await page.locator('[data-test=appearance-preview-dialog]').getByRole('button',{name:'关闭预览',exact:true}).click();assert.equal(await page.locator('[data-test=banner-title] input').inputValue(),'尚未保存的外观草稿');
  await page.locator('[data-test=banner-title] input').fill(before.content.banner.title);
  await page.locator('[data-test=save-content]').click();await page.getByText('首页设计已保存',{exact:true}).waitFor();
  const stored=await(await page.request.get(base+`/api/conferences/${eventId}/content`)).json();assert.equal(stored.template,'academic-full');assert.deepEqual(stored.content.theme,{...before.content.theme,layout:'simple-2',accent:'#3f67c8'});assert.deepEqual({...stored.content,theme:before.content.theme},before.content,'Choosing an appearance preserves content');
  await page.reload();await page.getByRole('tab',{name:'首页设计',exact:true}).click();await page.locator('[data-test=site-editor][data-ready=true]').waitFor();assert.equal(await page.locator('[data-test=appearance-simple-2-blue]').isChecked(),true);
  await page.locator('.site-color-field input').fill('#123456');assert.equal(await page.locator('[data-test=appearance-picker] input:checked').count(),0,'Custom accents must not select a preset');
  const orange=page.locator('[data-test=appearance-simple-1-orange]');await orange.focus();await page.keyboard.press('Space');assert.equal(await orange.isChecked(),true);await page.keyboard.press('ArrowRight');assert.equal(await page.locator('[data-test=appearance-simple-1-red]').isChecked(),true);
  for(const width of [390,320,1440]){await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Editor must fit ${width}px`);await page.locator('[data-test=appearance-picker]').screenshot({path:projectRoot+`/../output/appearance-picker-${width}.png`});}
  await page.locator('[data-test=preview-appearance]').click();await frame.locator('.appearance-simple-1').waitFor();await page.locator('[data-test=appearance-preview-frame]').screenshot({path:projectRoot+'/../output/appearance-preview-simple-1.png'});await page.locator('[data-test=appearance-preview-dialog]').getByRole('button',{name:'关闭预览',exact:true}).click();
  await page.route(`**/api/conferences/${eventId}/appearance-preview`,route=>route.fulfill({status:403,contentType:'application/json',body:JSON.stringify({message:'Forbidden'})}));await page.locator('[data-test=preview-appearance]').click();await page.locator('[data-test=content-error]').getByText(/会议已锁定/).waitFor();assert.equal(await page.locator('[data-test=appearance-simple-1-red]').isChecked(),true);assert.equal(await page.locator('[data-test=save-content]').isDisabled(),true);
  assert.deepEqual(errors,[]);Object.assign(result,{passed:true,twelve_presets:true,two_groups:true,preview_no_write:true,stored_content_only:true,simple_2_blue_saved:true,content_preserved:true,custom_accent:true,keyboard:true,mobile_390:true,mobile_320:true,preview_403_retains_draft:true,browser_errors:errors});
 }finally{
  await browser.close();if(fixture)python(`from indico.web.flask.app import make_app\nfrom indico.modules.users import User\nfrom indico.modules.events import Event\nfrom indico.core.db import db\napp=make_app()\nwith app.app_context():\n user=User.get(${fixture.id})\n assert user.email.startswith('appearance-ui-') and user.email.endswith('@example.invalid')\n for event in Event.query.filter_by(creator_id=user.id,is_deleted=False):\n  assert event.title.startswith('外观编辑验收 ')\n  event.is_deleted=True\n user.is_deleted=True\n db.session.commit()`);
 }
 fs.writeFileSync(projectRoot+'/../output/appearance-editor-flow.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
})().catch(e=>{console.error(e.message);process.exit(1)});

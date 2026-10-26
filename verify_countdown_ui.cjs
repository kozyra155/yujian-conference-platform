const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base='http://192.168.2.36:12880';
function python(code){return execFileSync('docker',['compose','-p','yujian-indico-v1','exec','-T','indico-web','/opt/indico/.venv/bin/python','-c',code],{cwd:__dirname,encoding:'utf8'});}
(async()=>{
 // Mocked HTML has no IP address space; allow its same-origin LAN assets in Chromium.
 const browser=await chromium.launch({args:['--disable-features=LocalNetworkAccessChecks']});let fixture,eventId;const errors=[];const result={};
 try{
  fixture=JSON.parse(python("import json,uuid\nfrom indico.web.flask.app import make_app\nfrom indico.modules.users.operations import create_user\nfrom indico.modules.auth import Identity\nfrom indico.core.db import db\napp=make_app(config_override={'EMAIL_BACKEND':'indico.vendor.django_mail.backends.locmem.EmailBackend','SMTP_USE_CELERY':False})\nwith app.test_request_context(base_url='http://192.168.2.36:12880'):\n username='countdown-ui-'+uuid.uuid4().hex[:12]\n password=uuid.uuid4().hex+'!A8'\n user=create_user(username+'@example.invalid',{'first_name':'倒计时验收','last_name':'临时'},Identity(provider='indico',identifier=username,password=password))\n db.session.commit()\n print(json.dumps({'id':user.id,'username':username,'password':password}))"));
  const context=await browser.newContext({locale:'zh-CN',viewport:{width:1440,height:1050},timezoneId:'America/New_York'});
  context.setDefaultTimeout(10000);
  await context.addInitScript(()=>localStorage.setItem('meet-language','zh'));
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await page.goto(base+'/login/');await page.locator('[name=identifier]').fill(fixture.username);await page.locator('[name=password]').fill(fixture.password);await Promise.all([page.waitForURL(u=>!u.pathname.startsWith('/login/')),page.locator('#login-form').evaluate(f=>f.requestSubmit())]);
  const session=await(await page.request.get(base+'/assets/js-vars/user.js?portal=1')).json();
  const created=await page.request.post(base+'/api/conferences/',{headers:{'X-CSRF-Token':session.csrf_token},data:{title:'倒计时验收 '+Date.now(),start:'2027-10-20T09:00',end:'2027-10-21T17:00',location:'武汉',description:'自动化临时会议。',template:'academic-full'}});
  assert.equal(created.status(),201);const conference=await created.json();eventId=conference.id;
  await page.goto(base+conference.builder_url);await page.getByRole('tab',{name:'首页设计',exact:true}).click();await page.locator('[data-test=site-editor][data-ready=true]').waitFor();
  assert.equal(await page.locator('[data-test=countdown-enabled]').getByRole('switch').isChecked(),false);
  await page.locator('[data-test=countdown-enabled]').click();
  await page.locator('[data-test=countdown-date]').fill('2027-11-02');
  async function save(){const response=page.waitForResponse(r=>r.request().method()==='PUT'&&new URL(r.url()).pathname===`/api/conferences/${eventId}/content`);await page.locator('[data-test=save-content]').click();assert.equal((await response).status(),200);await page.locator('[data-test=save-content]:not(.is-loading)').waitFor();}
  await save();let stored=await(await page.request.get(base+`/api/conferences/${eventId}/content`)).json();
  assert.deepEqual(stored.content.countdown,{enabled:true,target_date:'2027-11-02'});
  const publicPage=await context.newPage();publicPage.on('pageerror',e=>errors.push(e.message));
  await publicPage.goto(base+`/event/${eventId}/`);assert.equal(await publicPage.locator('[data-live-countdown]').getAttribute('data-target'),'2027-11-02T00:00:00+08:00');
  await page.locator('[data-test=countdown-date]').fill('');await save();
  await publicPage.reload();assert.equal(await publicPage.locator('[data-live-countdown]').getAttribute('data-target'),'2027-10-20T00:00:00+08:00');
  const html=await publicPage.content();
  const simulation=await browser.newContext({locale:'zh-CN',timezoneId:'America/New_York',viewport:{width:1440,height:1050}});
  await simulation.addInitScript(()=>localStorage.setItem('meet-language','zh'));
  const clockPage=await simulation.newPage();clockPage.on('pageerror',e=>errors.push(e.message));
  await clockPage.clock.install({time:new Date('2001-01-01T00:00:00Z')});await clockPage.clock.pauseAt(new Date('2001-01-01T00:00:01Z'));
  await clockPage.route(base+`/event/${eventId}/`,route=>route.fulfill({contentType:'text/html',body:html.replace(/data-now="[^"]+"/,'data-now="2027-09-07T17:41:45+08:00"')}));
  await clockPage.goto(base+`/event/${eventId}/`);
  const parts=()=>clockPage.locator('[data-countdown-part]').allTextContents();
  assert.deepEqual(await parts(),['42','06','18','15']);
  await clockPage.clock.runFor(1000);assert.deepEqual(await parts(),['42','06','18','14']);
  for(const layout of ['simple-1','simple-2']){
   await clockPage.locator('body').evaluate((b,layout)=>{b.classList.remove('appearance-simple-1','appearance-simple-2');b.classList.add('appearance-'+layout)},layout);
   for(const width of [1440,1024,760,390,320]){
    await clockPage.setViewportSize({width,height:1000});assert.equal(await clockPage.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${layout} fits ${width}`);
    const box=await clockPage.locator('[data-live-countdown]').boundingBox();assert.ok(box.width>150 && box.x>=0 && box.x+box.width<=width);
    if(layout==='simple-1' && [1440,390].includes(width))await clockPage.screenshot({path:__dirname+`/../output/countdown-${width}.png`,fullPage:true});
   }
  }
  await clockPage.locator('.language-toggle').click();await clockPage.getByText('Conference starts in:',{exact:true}).waitFor();assert.deepEqual(await parts(),['42','06','18','14']);
  await clockPage.clock.fastForward(20*86400*1000);
  await clockPage.clock.fastForward(20*86400*1000);
  await clockPage.clock.fastForward((2*86400+6*3600+18*60+14)*1000);
  assert.equal(await clockPage.locator('.complete-clock-running').isVisible(),false);
  assert.equal(await clockPage.locator('.complete-clock-ended').textContent(),'The conference has started');assert.deepEqual(await parts(),['0','00','00','00']);
  await clockPage.clock.runFor(2000);assert.deepEqual(await parts(),['0','00','00','00']);
  await page.locator('[data-test=countdown-date]').fill('2000-01-01');await save();await publicPage.reload();assert.equal(await publicPage.locator('.complete-clock-ended').textContent(),'目标日期已到');assert.equal(await publicPage.locator('.complete-clock-running').isVisible(),false);
  await page.locator('[data-test=countdown-enabled]').click();await save();await publicPage.reload();assert.equal(await publicPage.locator('[data-live-countdown]').count(),0);
  await page.reload();await page.getByRole('tab',{name:'首页设计',exact:true}).click();await page.locator('[data-test=site-editor][data-ready=true]').waitFor();assert.equal(await page.locator('[data-test=countdown-date]').inputValue(),'2000-01-01');assert.equal(await page.locator('[data-test=countdown-enabled]').getByRole('switch').isChecked(),false);
  for(const width of [390,320]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);}
  assert.deepEqual(errors,[]);Object.assign(result,{passed:true,editor_save_reload:true,custom_target:true,default_follows_conference_date:true,beijing_midnight_in_foreign_timezone:true,server_clock_ignores_wrong_client_date:true,live_seconds:true,expiry_no_negative:true,custom_expiry:true,language_switch:true,disable_preserves_settings:true,two_layouts_five_widths:true,browser_errors:errors});
 }finally{
  await browser.close();if(fixture)python(`from indico.web.flask.app import make_app\nfrom indico.modules.users import User\nfrom indico.modules.events import Event\nfrom indico.core.db import db\napp=make_app()\nwith app.app_context():\n user=User.get(${fixture.id})\n assert user.email.startswith('countdown-ui-') and user.email.endswith('@example.invalid')\n for event in Event.query.filter_by(creator_id=user.id,is_deleted=False):\n  assert event.title.startswith('倒计时验收 ')\n  event.is_deleted=True\n user.is_deleted=True\n db.session.commit()`);
 }
 fs.writeFileSync(__dirname+'/../output/countdown-verification.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
})().catch(e=>{console.error(e.stack);process.exit(1)});

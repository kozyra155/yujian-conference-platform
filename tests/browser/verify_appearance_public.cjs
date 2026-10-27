const projectRoot=require('node:path').resolve(__dirname,'../..');
const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');const fs=require('node:fs');
const base='http://192.168.2.36:12880';
function python(code){return execFileSync('docker',['compose','-p','yujian-indico-v1','exec','-T','indico-web','/opt/indico/.venv/bin/python','-c',code],{cwd:projectRoot,encoding:'utf8'});}
(async()=>{
 const browser=await chromium.launch();let fixture,eventId,result;
 try{
  fixture=JSON.parse(python("import json,uuid\nfrom indico.web.flask.app import make_app\nfrom indico.modules.users.operations import create_user\nfrom indico.modules.auth import Identity\nfrom indico.core.db import db\napp=make_app(config_override={'EMAIL_BACKEND':'indico.vendor.django_mail.backends.locmem.EmailBackend','SMTP_USE_CELERY':False})\nwith app.test_request_context(base_url='http://192.168.2.36:12880'):\n name='appearance-public-'+uuid.uuid4().hex[:12]\n password=uuid.uuid4().hex+'!A8'\n user=create_user(name+'@example.invalid',{'first_name':'外观验收','last_name':'临时账号'},Identity(provider='indico',identifier=name,password=password))\n db.session.commit()\n print(json.dumps({'id':user.id,'username':name,'password':password}))"));
  const ctx=await browser.newContext({locale:'zh-CN',viewport:{width:1440,height:1000}});ctx.setDefaultTimeout(12000);await ctx.addInitScript(()=>localStorage.setItem('meet-language','zh'));
  const p=await ctx.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(base+'/login/');await p.locator('[name=identifier]').fill(fixture.username);await p.locator('[name=password]').fill(fixture.password);await Promise.all([p.waitForURL(u=>!u.pathname.startsWith('/login/')),p.locator('#login-form').evaluate(f=>f.requestSubmit())]);
  const session=await(await p.request.get(base+'/assets/js-vars/user.js?portal=1')).json();const headers={'X-CSRF-Token':session.csrf_token};
  const created=await p.request.post(base+'/api/conferences/',{headers,data:{title:'外观展示验收 '+Date.now(),start:'2027-10-20T09:00',end:'2027-10-22T17:00',location:'示例会场',description:'APPEARANCE-CONTENT-PRESERVED 外观切换不改变会议内容。',template:'academic-full'}});assert.equal(created.status(),201);eventId=(await created.json()).id;
  let payload=await(await p.request.get(base+`/api/conferences/${eventId}/content`)).json();assert.equal(payload.appearances?.length,12,'Twelve appearances must be available');
  payload.content.speakers=[{name:'示例嘉宾',name_en:'Example speaker',affiliation:'示例单位',affiliation_en:'Example institute',topic:'示例主题',topic_en:'Example topic',image:'',enabled:true}];payload.content.news=[{title:'示例动态',title_en:'Example news',date:'2026-10-15',body:'切换外观后仍然保留。',body_en:'Retained when changing appearance.',url:'',enabled:true}];payload.content.organizations[0].items=[{name:'示例组织',name_en:'Example organization',image:'',url:'',enabled:true}];
  let saved=await p.request.put(base+`/api/conferences/${eventId}/content`,{headers,data:{revision:payload.revision,content:payload.content}});assert.equal(saved.status(),200);payload=await saved.json();
  assert.equal((await p.request.post(base+`/api/conferences/${eventId}/publication`,{headers,data:{published:true}})).status(),200);
  const guest=await browser.newContext({viewport:{width:1440,height:1000}});await guest.addInitScript(()=>localStorage.setItem('meet-language','zh'));const q=await guest.newPage();q.on('pageerror',e=>errors.push(e.message));
  const shapes={};
  for(const preset of payload.appearances){
   payload.content.theme={layout:preset.layout,accent:preset.accent};saved=await p.request.put(base+`/api/conferences/${eventId}/content`,{headers,data:{revision:payload.revision,content:payload.content}});assert.equal(saved.status(),200);payload=await saved.json();assert.equal((await q.goto(base+`/event/${eventId}/`)).status(),200);await q.waitForFunction(()=>window.MeetPortal?.language==='zh');
   assert.ok(await q.locator('body').evaluate((b,layout)=>b.classList.contains('appearance-'+layout),preset.layout));assert.equal((await q.locator('body').evaluate(b=>getComputedStyle(b).getPropertyValue('--complete-accent'))).trim(),preset.accent);
   assert.match(await q.locator('#main').innerText(),/APPEARANCE-CONTENT-PRESERVED/);assert.equal(await q.locator('.complete-speaker').count(),1);assert.equal(await q.locator('.complete-news-item').count(),1);assert.equal(await q.locator('#complete-menu>li').count(),9);assert.equal(await q.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,preset.id);
   if(preset.id.endsWith('-blue')){
    const nav=await q.locator('.complete-navigation').boundingBox(),hero=await q.locator('.complete-banner').boundingBox();shapes[preset.layout]={nav,hero};
    await q.screenshot({path:projectRoot+`/../output/appearance-${preset.layout}-desktop.png`,fullPage:true});
    for(const width of [320,390,760,1440]){await q.setViewportSize({width,height:900});assert.equal(await q.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${preset.id} at ${width}`);}
    await q.setViewportSize({width:390,height:900});await q.locator('.complete-mobile-toggle').click();await q.getByRole('link',{name:'会议组织',exact:true}).waitFor();await q.locator('.complete-mobile-toggle').click();await q.screenshot({path:projectRoot+`/../output/appearance-${preset.layout}-mobile.png`,fullPage:true});await q.setViewportSize({width:1440,height:1000});
   }
  }
  assert.ok(shapes['simple-1'].nav.y>=shapes['simple-1'].hero.y+shapes['simple-1'].hero.height-2,'Simple 1 has horizontal navigation below banner');assert.ok(shapes['simple-2'].nav.x+shapes['simple-2'].nav.width<=shapes['simple-2'].hero.x+2,'Simple 2 has actual left navigation');
  assert.deepEqual(errors,[]);result={passed:true,appearances:12,all_saved_and_rendered:true,content_preserved:true,navigation_preserved:true,two_distinct_layouts:true,responsive_widths:[320,390,760,1440],browser_errors:errors};
 }finally{
  await browser.close();if(fixture)python(`from indico.web.flask.app import make_app\nfrom indico.modules.users import User\nfrom indico.modules.events import Event\nfrom indico.core.db import db\napp=make_app()\nwith app.app_context():\n u=User.get(${fixture.id})\n assert u.email.startswith('appearance-public-') and u.email.endswith('@example.invalid')\n for e in Event.query.filter_by(creator_id=u.id,is_deleted=False):\n  assert e.title.startswith('外观展示验收 ')\n  e.is_deleted=True\n u.is_deleted=True\n db.session.commit()`);
 }
 fs.writeFileSync(projectRoot+'/../output/appearance-public-flow.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
})().catch(e=>{console.error(e.message);process.exit(1)});

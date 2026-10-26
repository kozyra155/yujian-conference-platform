const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base='http://192.168.2.36:12880';
function python(code){return execFileSync('docker',['compose','-p','yujian-indico-v1','exec','-T','indico-web','/opt/indico/.venv/bin/python','-c',code],{cwd:__dirname,encoding:'utf8'});}
const image=n=>({name:`feedback-${n}.png`,mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=','base64')});
(async()=>{
 const browser=await chromium.launch();let fixture,eventId;
 try{
  fixture=JSON.parse(python("import json,uuid\nfrom indico.web.flask.app import make_app\nfrom indico.modules.users.operations import create_user\nfrom indico.modules.auth import Identity\nfrom indico.core.db import db\napp=make_app(config_override={'EMAIL_BACKEND':'indico.vendor.django_mail.backends.locmem.EmailBackend','SMTP_USE_CELERY':False})\nwith app.test_request_context(base_url='http://192.168.2.36:12880'):\n name='feedback-ui-'+uuid.uuid4().hex[:12]\n password=uuid.uuid4().hex+'!A8'\n u=create_user(name+'@example.invalid',{'first_name':'测试反馈','last_name':'临时账号'},Identity(provider='indico',identifier=name,password=password))\n db.session.commit()\n print(json.dumps({'id':u.id,'username':name,'password':password}))"));
  const context=await browser.newContext({locale:'zh-CN',viewport:{width:1440,height:1000}});
  await context.addInitScript(()=>localStorage.setItem('meet-language','zh'));
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await page.goto(base+'/login/');await page.locator('[name=identifier]').fill(fixture.username);await page.locator('[name=password]').fill(fixture.password);
  await Promise.all([page.waitForURL(u=>!u.pathname.startsWith('/login/')),page.locator('#login-form').evaluate(f=>f.requestSubmit())]);
  const session=await(await page.request.get(base+'/assets/js-vars/user.js?portal=1')).json();const headers={'X-CSRF-Token':session.csrf_token};
  const created=await page.request.post(base+'/api/conferences/',{headers,data:{title:'测试反馈验收 '+Date.now(),start:'2027-10-20T09:00',end:'2027-10-21T17:00',location:'武汉',description:'测试反馈专用临时会议。',template:'academic-full'}});
  assert.equal(created.status(),201);const event=await created.json();eventId=event.id;
  await page.goto(base+event.builder_url+'?tab=design');await page.locator('[data-test=site-editor][data-ready=true]').waitFor();
  assert.equal(await page.locator('[data-test=gallery-introduction]').count(),1,'Introduction must support an image gallery');
  await page.locator('[data-test=add-speaker]').click();await page.locator('[data-test=speaker-name] input').fill('测试嘉宾 教授');
  await page.locator('[data-test=speakers-role] input').fill('特邀嘉宾');await page.locator('[data-test=speakers-bio] textarea').fill('嘉宾研究简介。');
  const gallery=page.locator('[data-test=gallery-introduction]');await gallery.locator('input[type=file]').setInputFiles([image(1),image(2)]);
  await gallery.locator('img').nth(1).waitFor();
  await page.locator('[data-test=add-committee]').click();const committee=page.locator('[data-test=committee-item]').first();await committee.getByLabel('组织名称',{exact:true}).fill('程序委员会');
  await committee.getByRole('button',{name:'添加成员',exact:true}).click();await committee.getByLabel('姓名与职称',{exact:true}).fill('委员会成员 教授');
  await page.locator('[data-test=add-topic]').click();await page.locator('[data-test=topics-title] input').fill('人工智能');await page.locator('[data-test=topics-keywords] textarea').fill('机器学习\n医学影像');
  await page.locator('[data-test=section-committees] .el-switch').click();await page.locator('[data-test=section-topics] .el-switch').click();
  const showcases=page.locator('[data-test=choices-showcase]');await showcases.locator('.el-select').click();await page.getByRole('option',{name:'论文与报告',exact:true}).click();await page.keyboard.press('Escape');await page.locator('[data-test=section-showcase] .el-switch').click();
  const matchmaking=page.locator('[data-test=matchmaking-editor]');await matchmaking.locator('.el-switch').click();await matchmaking.getByLabel('活动介绍',{exact:true}).fill('开展技术交流与成果合作。');await page.locator('[data-test=section-matchmaking] .el-switch').click();
  const rich=page.locator('[data-test=contact-richtext]');await rich.getByRole('textbox').fill('请联系会议秘书处。');await rich.getByRole('button',{name:'插入表格',exact:true}).click();assert.equal(await rich.locator('table').count(),1);
  const contactSection=rich.locator('xpath=..');await contactSection.locator('summary').click();await contactSection.locator('.rich-input').nth(1).fill('English contact details');
  await page.getByLabel('报名须知',{exact:true}).fill('请根据参会身份报名。');await page.getByLabel('投稿须知',{exact:true}).fill('请使用会议模板提交摘要。');
  await page.locator('[data-test=section-registration_info] .el-switch').click();await page.locator('[data-test=section-submission_info] .el-switch').click();
  const group=page.locator('[data-test=organization-group]').first();await group.locator('[data-test=add-organization-item]').click();await group.getByLabel('单位名称',{exact:true}).fill('测试单位');
  await group.getByLabel('单位简介（300字以内）',{exact:true}).fill('测试单位介绍');await group.locator('[data-test=organization-images] input[type=file]').setInputFiles([image(3),image(4)]);await group.locator('[data-test=organization-images] img').nth(1).waitFor();
  await page.locator('[data-test=save-content]').click();await page.getByText('首页设计已保存',{exact:true}).waitFor();
  let stored=await(await page.request.get(base+`/api/conferences/${eventId}/content`)).json();
  assert.equal(stored.content.introduction_images.length,2);assert.equal(stored.content.speakers[0].bio,'嘉宾研究简介。');assert.equal(stored.content.committees[0].members[0].name,'委员会成员 教授');assert.equal(stored.content.topics[0].keywords,'机器学习\n医学影像');assert.equal(stored.content.organizations[0].items[0].images.length,2);assert.match(stored.content.contact.html,/<table/);assert.deepEqual(stored.content.showcase,['论文与报告']);assert.equal(stored.content.matchmaking.enabled,true);
  await group.getByLabel('单位网址（可选）',{exact:true}).fill('javascript:alert(1)');await page.locator('[data-test=save-content]').click();
  await page.locator('[data-test=content-error]').getByText(/organizations\[0\].items\[0\].url/).waitFor();assert.equal(await group.getByLabel('单位网址（可选）',{exact:true}).inputValue(),'javascript:alert(1)');
  assert.equal((await(await page.request.get(base+`/api/conferences/${eventId}/content`)).json()).revision,stored.revision,'Rejected saves must not advance revision');
  await group.getByLabel('单位网址（可选）',{exact:true}).fill('');
  const publicPage=await context.newPage();await publicPage.goto(base+event.url);assert.equal(await publicPage.locator('#committees').count(),1);assert.equal(await publicPage.locator('#topics').count(),1);assert.equal(await publicPage.locator('#introduction img').count(),2);assert.equal(await publicPage.locator('#showcase').getByText('论文与报告',{exact:true}).count(),1);assert.equal(await publicPage.locator('#matchmaking a[href$="/interest/"]').count(),1);
  assert.equal(await publicPage.locator('#registration-info').count(),1);assert.equal(await publicPage.locator('#submission-info').count(),1);
  await publicPage.locator('.language-toggle').click();await publicPage.getByText('English contact details',{exact:true}).waitFor();assert.equal(await publicPage.locator('#introduction [data-complete-language=zh]').isVisible(),true,'English contact must not hide an introduction with no English translation');
  for(const width of [390,320]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Editor overflow at ${width}`);}
  await page.screenshot({path:__dirname+'/../output/feedback-editor-mobile.png',fullPage:true});await page.locator('[data-test=committee-item]').screenshot({path:__dirname+'/../output/feedback-committee-mobile.png'});await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:__dirname+'/../output/feedback-editor-desktop.png',fullPage:true});await group.screenshot({path:__dirname+'/../output/feedback-organizations-desktop.png'});
  assert.deepEqual(errors,[]);fs.writeFileSync(__dirname+'/../output/feedback-editor-result.json',JSON.stringify({passed:true,multi_upload:true,guest_bio:true,committees:true,topics:true,contact_table:true,precise_save_error:true,retained_draft:true,mobile_320_390:true},null,2));console.log('Feedback editor: passed');
 }finally{
  await browser.close();if(fixture)python(`from indico.web.flask.app import make_app\nfrom indico.modules.users import User\nfrom indico.modules.events import Event\nfrom indico.core.db import db\napp=make_app(config_override={'EMAIL_BACKEND':'indico.vendor.django_mail.backends.locmem.EmailBackend','SMTP_USE_CELERY':False})\nwith app.app_context():\n u=User.get(${fixture.id})\n assert u.email.startswith('feedback-ui-') and u.email.endswith('@example.invalid')\n for e in Event.query.filter_by(creator_id=u.id,is_deleted=False):\n  assert e.id not in (22,61,171) and e.title.startswith('测试反馈验收 ')\n  e.is_deleted=True\n u.is_deleted=True\n db.session.commit()`);
 }
})().catch(e=>{console.error(e.message);process.exit(1)});

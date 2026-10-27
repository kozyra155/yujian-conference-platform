const projectRoot=require('node:path').resolve(__dirname,'../..');
const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base='http://192.168.2.36:12880';
(async()=>{
 const browser=await chromium.launch({headless:true});let createdId,result;
 const title=`界面建站验收 ${Date.now()}`;
 try{
  const page=await browser.newPage({locale:'zh-CN',viewport:{width:1440,height:1000}});
  await page.addInitScript(()=>localStorage.setItem('meet-language','zh'));
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/login/');
  const account=JSON.parse(fs.readFileSync(projectRoot+'/demo-accounts.json','utf8')).find(a=>a.username==='host-a');
  await page.locator('[name=identifier]').fill(account.username);await page.locator('[name=password]').fill(account.password);
  await Promise.all([page.waitForURL(u=>!u.pathname.startsWith('/login/')),page.locator('#login-form').evaluate(f=>f.requestSubmit())]);
  await page.goto(base+'/category/1/#create-event:conference:1');await page.waitForURL('**/conference/create/');
  await page.locator('[data-workspace-ready]').waitFor();
  await page.locator('[name=title]').fill(title);
  await page.locator('[name=start]').fill('2027-09-20 09:00');await page.locator('[name=start]').press('Tab');
  await page.locator('[name=end]').fill('2027-09-21 17:00');await page.locator('[name=end]').press('Tab');
  await page.locator('[name=location]').fill('武汉');
  await page.locator('textarea[name=description]').fill('自动化界面验收临时会议，测试后删除。');
  const posted=page.waitForResponse(r=>r.url()===base+'/api/conferences/'&&r.request().method()==='POST');
  await page.locator('#builder-form button[type=submit]').click();
  const response=await posted;assert.equal(response.status(),201);
  await page.waitForURL(/\/conference\/\d+\/$/);
  createdId=Number(new URL(page.url()).pathname.split('/')[2]);
  const event=(await(await page.request.get(base+'/api/organizer/conferences/')).json()).events.find(e=>e.id===createdId);
  assert.equal(event.title,title);assert.equal(event.published,false);
  await page.locator('[data-workspace-ready]').waitFor();
  assert.equal(await page.locator('#builder-state').innerText(),'私密草稿');
  assert.match(await page.locator('.website-summary h2').innerText(),/界面建站验收/);
  const anon=await browser.newPage();const draft=await anon.goto(base+event.url);
  assert.ok(draft.status()===403||new URL(anon.url()).pathname.startsWith('/login/'));
  assert.deepEqual(errors,[]);
  result={passed:true,real_component_form_post:true,dates_parsed:true,native_hash_redirect:true,draft_created:true,anonymous_denied:true,browser_errors:errors};
 }finally{
  await browser.close();
  if(createdId){
   assert.ok(Number.isInteger(createdId));
   const code=`from indico.web.flask.app import make_app\nfrom indico.core.db import db\nfrom indico.modules.events import Event\napp=make_app()\nwith app.app_context():\n e=Event.get(${createdId})\n assert e.title.startswith('界面建站验收 ')\n e.is_deleted=True\n db.session.commit()`;
   execFileSync('docker',['compose','-p','yujian-indico-v1','exec','-T','indico-web','/opt/indico/.venv/bin/python','-c',code],{cwd:projectRoot,stdio:'pipe'});
  }
 }
 fs.writeFileSync(projectRoot+'/../output/workspace-creation.json',JSON.stringify(result,null,2));
 console.log(JSON.stringify(result));
})().catch(e=>{console.error(e);process.exit(1)});

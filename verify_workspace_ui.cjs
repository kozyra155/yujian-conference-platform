const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base='http://192.168.2.36:12880';
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({locale:'zh-CN',viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>localStorage.setItem('meet-language','zh'));
  await page.goto(base+'/category/1/');
  await page.locator('[data-workspace-ready]').waitFor({timeout:8000});
  assert.equal(await page.locator('.el-input').count()>0,true);
  await page.screenshot({path:__dirname+'/../output/yujian-directory-desktop.png',fullPage:true,animations:'disabled'});
  await page.route('**/api/conferences/?*',async route=>{
   const q=new URL(route.request().url()).searchParams.get('q');
   if(!['first','second'].includes(q))return route.continue();
   if(q==='first')await new Promise(resolve=>setTimeout(resolve,650));
   await route.fulfill({json:{events:[{id:9999,title:q,url:'/event/9999/',start:'2027-07-10T01:00:00Z',end:'2027-07-12T09:00:00Z',location:'Test',description:''}],total:1,page:1}});
  });
  const search=page.locator('.search-field input');
  const oldResponse=page.waitForResponse(r=>r.url().includes('q=first'));
  await search.fill('first');await page.locator('.search-field button').click();
  await search.fill('second');await page.locator('.search-field button').click();
  await page.locator('.directory-card h3').getByRole('link',{name:'second',exact:true}).waitFor();
  await(await oldResponse).finished();
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  assert.equal(await page.locator('.directory-card h3').innerText(),'second');
  await page.unroute('**/api/conferences/?*');
  await page.goto(base+'/category/1/#create-event:conference:1');
  await page.waitForURL('**/login/**');
  const account=JSON.parse(fs.readFileSync(__dirname+'/demo-accounts.json','utf8')).find(a=>a.username==='host-a');
  await page.locator('[name=identifier]').fill(account.username);
  await page.locator('[name=password]').fill(account.password);
  await Promise.all([page.waitForURL(u=>!u.pathname.startsWith('/login/')),page.locator('#login-form').evaluate(f=>f.requestSubmit())]);
  await page.goto(base+'/user/dashboard/');
  await page.locator('[data-workspace-ready]').waitFor();
  assert.equal(await page.locator('.el-table').count(),1);
  await page.screenshot({path:__dirname+'/../output/yujian-dashboard-desktop.png',fullPage:true,animations:'disabled'});
  for(const path of ['/category/1/','/user/dashboard/','/conference/create/','/conference/4/']){
   await page.goto(base+path);await page.locator('[data-workspace-ready]').waitFor();
   for(const width of [320,390,760,1440]){
    await page.setViewportSize({width,height:900});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${path} overflow ${width}`);
   }
  }
  await page.goto(base+'/conference/create/');await page.locator('[data-workspace-ready]').waitFor();
  await page.setViewportSize({width:320,height:900});
  await page.locator('[name=start]').click();await page.locator('.el-picker-panel:visible').waitFor();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Mobile date picker overflow');
  await page.keyboard.press('Escape');
  await page.goto(base+'/conference/4/');await page.locator('[data-workspace-ready]').waitFor();
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.locator('.mobile-participation').isVisible(),true);
  await page.screenshot({path:__dirname+'/../output/yujian-workspace-mobile.png',fullPage:true,animations:'disabled'});
  await page.locator('.language-toggle').click();
  await page.getByRole('heading',{name:'Website workspace',exact:true}).waitFor();
  await page.locator('.language-toggle').click();
  await page.setViewportSize({width:1440,height:1000});
  await page.goto(base+'/event/4/');await page.locator('.conference-banner').waitFor();
  await page.screenshot({path:__dirname+'/../output/yujian-site-desktop.png',fullPage:true});
  for(const width of [320,390,760,1440]){
   await page.setViewportSize({width,height:900});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`site overflow ${width}`);
  }
  await page.locator('.language-toggle').click();
  await page.getByText('Important dates',{exact:true}).waitFor();
  assert.match(await page.title(),/遇见科技一键建站体验会议/);
  assert.deepEqual(errors,[]);
  const result={passed:true,native_category:true,native_dashboard:true,element_plus:true,public_theme:true,language:true,search_response_order:true,mobile_participation_entry:true,mobile_date_picker:true,responsive:[320,390,760,1440],browser_errors:errors};
  fs.writeFileSync(__dirname+'/../output/workspace-ui.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

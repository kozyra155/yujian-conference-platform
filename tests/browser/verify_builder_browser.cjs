const projectRoot=require('node:path').resolve(__dirname,'../..');
const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base='http://192.168.2.36:12880';
async function togglePublication(page){
  await page.locator('#builder-publish').click();
  await page.locator('.el-message-box').getByRole('button',{name:/确认发布|确认撤回|^Publish$|^Withdraw$/}).click();
}
(async()=>{
  const browser=await chromium.launch({headless:true});
  const errors=[];
  try{
    const context=await browser.newContext({locale:'zh-CN',viewport:{width:1440,height:1000}});
    await context.addInitScript(()=>localStorage.setItem('meet-language','zh'));
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base+'/register/');
    await page.locator('#email').fill('draft@example.com');
    await page.locator('.language-toggle').click();
    await page.waitForFunction(async()=>JSON.parse(await(await fetch('/assets/js-vars/user.js?portal=1')).text()).language==='en_GB');
    assert.equal(await page.locator('#email').inputValue(),'draft@example.com');
    await page.locator('.language-toggle').click();
    await page.goto(base+'/login/');
    const account=JSON.parse(fs.readFileSync(projectRoot+'/demo-accounts.json','utf8')).find(a=>a.username==='host-a');
    await page.locator('input[name=identifier]').fill(account.username);
    await page.locator('input[name=password]').fill(account.password);
    await Promise.all([page.waitForURL(u=>!u.pathname.startsWith('/login/')),page.locator('#login-form').evaluate(f=>f.requestSubmit())]);
    await page.goto(base+'/#create-event:conference');
    await page.waitForURL('**/conference/create/');
    await page.locator('[data-workspace-ready]').waitFor();
    await page.locator('#builder-form').waitFor();
    await page.locator('[name=title]').fill('遇见科技一键建站体验会议');
    await page.locator('[name=start]').fill('2027-07-10 09:00');
    await page.locator('[name=start]').press('Tab');
    await page.locator('[name=end]').fill('2027-07-12 17:00');
    await page.locator('[name=end]').press('Tab');
    await page.locator('[name=location]').fill('武汉');
    await page.locator('textarea[name=description]').fill('本会议用于展示遇见科技一键建站流程，不接受真实报名。主办方可独立编辑栏目、预览和发布网站。');
    await page.screenshot({path:projectRoot+'/../output/yujian-builder-create-desktop.png',fullPage:true,animations:'disabled'});
    await page.setViewportSize({width:320,height:900});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await page.screenshot({path:projectRoot+'/../output/yujian-builder-create-mobile.png',fullPage:true,animations:'disabled'});
    await page.setViewportSize({width:1440,height:1000});
    const mine=await(await page.request.get(base+'/api/organizer/conferences/')).json();
    const existing=mine.events.find(e=>e.title==='遇见科技一键建站体验会议');
    if(existing)await page.goto(base+existing.builder_url);
    else await Promise.all([page.waitForURL(/\/conference\/\d+\//),page.locator('#builder-form button[type=submit]').click()]);
    const id=Number(new URL(page.url()).pathname.split('/')[2]);
    await page.waitForFunction(()=>document.querySelector('#builder-state')?.textContent.length>0);
    const state=await page.locator('#builder-state').innerText();
    if(state==='已发布')await togglePublication(page);
    await page.waitForFunction(()=>document.querySelector('#builder-state')?.textContent==='私密草稿');
    const anon=await browser.newPage({locale:'zh-CN'});
    anon.on('pageerror',e=>errors.push(e.message));
    let protectedResponse=await anon.goto(base+`/event/${id}/`);
    assert.ok(protectedResponse.status()===403||new URL(anon.url()).pathname.startsWith('/login/'));
    await page.locator(`.next-steps a[href="/event/${id}/manage/layout/menu/"]`).click();
    await page.screenshot({path:projectRoot+'/../output/yujian-native-editor-desktop.png',fullPage:true,animations:'disabled'});
    await page.locator('.menu-entry').filter({hasText:'会议委员会'}).first().locator('.edit-entry').click();
    const editor=page.frameLocator('iframe.tox-edit-area__iframe').locator('body');
    await editor.waitFor();
    await editor.fill('委员会内容编辑验收：遇见科技会议服务团队。');
    await page.waitForFunction(()=>document.querySelector('.ui-dialog input[name=html]')?.value.includes('委员会内容编辑验收'));
    const saved=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().includes('/manage/layout/menu/'));
    await page.locator('.ui-dialog input[type=submit]').click();
    assert.ok((await(await saved).json()).entry);
    await page.goto(base+`/conference/${id}/`);
    await page.waitForFunction(()=>document.querySelector('#builder-state')?.textContent==='私密草稿');
    await togglePublication(page);
    await page.waitForFunction(()=>document.querySelector('#builder-state')?.textContent==='已发布');
    await anon.goto(base+`/event/${id}/`);
    const committeeUrl=await anon.getByRole('link',{name:'会议委员会',exact:true}).getAttribute('href');
    for(const width of [320,390,760,1440]){
      await anon.setViewportSize({width,height:900});
      for(const url of [`/event/${id}/`,committeeUrl]){
        await anon.goto(new URL(url,base).href);
        assert.equal(await anon.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Public site overflow ${width} ${url}`);
        if(width===390)await anon.screenshot({path:projectRoot+`/../output/yujian-site-${url===committeeUrl?'page-':''}mobile.png`,fullPage:true,animations:'disabled'});
      }
    }
    assert.equal(await page.locator('#builder-share').isVisible(),true);
    await page.screenshot({path:projectRoot+'/../output/yujian-builder-published-desktop.png',fullPage:true,animations:'disabled'});
    assert.equal((await anon.goto(base+`/event/${id}/`)).status(),200);
    await anon.getByRole('link',{name:'会议委员会',exact:true}).click();
    assert.match(await anon.locator('body').innerText(),/委员会内容编辑验收/);
    await anon.goto(base+'/events/');
    await anon.locator('[data-public-conferences]').getByRole('link',{name:'遇见科技一键建站体验会议',exact:true}).waitFor();
    await anon.locator('#conference-query').fill('武汉');
    await Promise.all([anon.waitForResponse(r=>r.url().includes('/api/conferences/?')&&r.url().includes('q=')),anon.locator('.conference-search button').click()]);
    await anon.locator('[data-public-conferences]').getByRole('link',{name:'遇见科技一键建站体验会议',exact:true}).waitFor();
    await anon.goto(base);
    await anon.locator('.conference-search input').fill('武汉');
    await Promise.all([anon.waitForResponse(r=>r.url().includes('/api/conferences/?')&&r.url().includes('q=')),anon.locator('.conference-search button').click()]);
    await anon.locator('[data-public-conferences]').getByRole('link',{name:'遇见科技一键建站体验会议',exact:true}).waitFor();
    await togglePublication(page);
    await page.waitForFunction(()=>document.querySelector('#builder-state')?.textContent==='私密草稿');
    protectedResponse=await anon.goto(base+`/event/${id}/`);
    assert.ok(protectedResponse.status()===403||new URL(anon.url()).pathname.startsWith('/login/'));
    assert.equal((await(await anon.request.get(base+'/api/conferences/')).json()).events.some(e=>e.id===id),false);
    // Keep one clearly labeled demonstration website for the user's acceptance review.
    await togglePublication(page);
    await page.waitForFunction(()=>document.querySelector('#builder-state')?.textContent==='已发布');
    for(const width of [320,390,760,1440]){
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Builder overflow ${width}`);
    }
    await page.locator('.language-toggle').click();
    await page.waitForFunction(()=>document.querySelector('#builder-state')?.textContent==='Published');
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:projectRoot+'/../output/yujian-builder-published-mobile-en.png',fullPage:true,animations:'disabled'});
    assert.deepEqual(errors,[]);
    const result={passed:true,event_id:id,website:base+`/event/${id}/`,register_input_preserved:true,create_hash_fixed:true,
      create_ui:true,editor_saved:true,draft_private:true,publish_public:true,live_listing:true,location_search:true,
      withdraw_private:true,language:true,overflow_widths:[320,390,760,1440],browser_errors:errors};
    result.public_site_mobile=true;
    fs.writeFileSync(projectRoot+'/../output/site-builder-browser.json',JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

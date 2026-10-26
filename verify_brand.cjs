const {chromium} = require('D:/playwright-demo/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async()=>{
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:1440,height:1000},locale:'zh-CN'});
  const failures=[];
  page.on('pageerror',error=>failures.push(error.message));
  page.on('response',response=>{if(response.url().includes('/portal-assets/')&&response.status()>=400)failures.push(response.url());});
  try {
    await page.goto('http://192.168.2.36:12880/');
    assert.match(await page.locator('.brand img').getAttribute('src'),/meet-logo\.png$/,'首页须使用用户提供的 Logo');
    assert.match(await page.locator('.hero-art').getAttribute('src'),/meet-background\.png$/);
    assert.equal(await page.locator('.brand img').evaluate(e=>e.complete&&e.naturalWidth>0),true);
    await page.screenshot({path:__dirname+'/../output/yujian-brand-desktop.png',fullPage:true});
    await page.goto('http://192.168.2.36:12880/login/');
    await page.locator('input[name="identifier"]').waitFor();
    assert.match(await page.locator('.header-logo').getAttribute('src'),/meet-logo\.png$/);
    assert.match(await page.title(),/遇见科技/);
    assert.equal(await page.locator('input[name="identifier"]').getAttribute('placeholder'),'用户名或邮箱');
    assert.equal(await page.locator('.login-form-button').innerText(),'登录');
    assert.ok(await page.locator('#login-form input[name="csrf_token"]').count(),'保留原有 CSRF 防护');
    await page.screenshot({path:__dirname+'/../output/yujian-login-desktop.png',fullPage:true});
    for(const width of [320,390,760,1024,1440]){
      await page.setViewportSize({width,height:844});
      for(const route of ['/','/login/']){
        await page.goto('http://192.168.2.36:12880'+route);
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${route} ${width}px 溢出`);
        if(width===390)await page.screenshot({path:__dirname+`/../output/yujian-${route==='/'?'brand':'login'}-mobile.png`,fullPage:true});
      }
    }
    const accounts=JSON.parse(fs.readFileSync(__dirname+'/demo-accounts.json','utf8'));
    const host=accounts.find(a=>a.username==='host-a');
    await page.locator('input[name="identifier"]').fill(host.username);
    await page.locator('input[name="password"]').fill(host.password);
    await Promise.all([page.waitForURL(url=>!url.pathname.startsWith('/login/')),page.locator('.login-form-button').click()]);
    assert.equal((await page.goto('http://192.168.2.36:12880/event/1/manage/layout/menu/')).status(),200);
    assert.equal((await page.goto('http://192.168.2.36:12880/event/2/manage/layout/menu/')).status(),403);
    assert.deepEqual(failures,[]);
    const result={passed:true,user_logo:true,user_background:true,login_brand:true,csrf_preserved:true,real_login:true,other_host_denied:true,responsive_widths:[320,390,760,1024,1440],browser_errors:failures};
    fs.writeFileSync(__dirname+'/brand-verification.json',JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});

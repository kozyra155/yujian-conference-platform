// Run after the isolated Python check and copying /tmp/registration-feedback-ui.json locally.
const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base='http://192.168.2.36:12880';
const fixtures=JSON.parse(fs.readFileSync(__dirname+'/.registration-feedback-ui.json','utf8'));
(async()=>{
  const browser=await chromium.launch({headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000},locale:'zh-CN'});
    const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('response',response=>{if(response.status()>=400)errors.push(response.status()+' '+new URL(response.url()).pathname);});
    // A mocked document has no LAN address space; fetch its real assets through the test driver.
    await page.route('**/*',async route=>route.fulfill({response:await route.fetch()}));
    await page.route('**/register/**',route=>route.fulfill({status:200,contentType:'text/html',body:fixtures.waiting}));
    await page.goto(base+'/register/');
    await page.waitForFunction(()=>window.MeetPortal&&typeof recovery!=='undefined');
    await page.locator('.meet-register-link-recovery summary').click();
    for(const value of ['https://evil.example/register/?token=fixture',base+'/login/?token=fixture',
      base+'/register/?token=fixture&next=https://evil.example/',
      base+'/register/?token=fixture&next=/event/123/../22/',
      base+'/register/?token=a&token=b',base+'/register/?token=fixture&next=/event/999999999999/']){
      await page.locator('#verification-link').fill(value);
      await page.locator('[data-verification-link-form] button').click();
      assert.equal(await page.locator('[data-verification-link-error]').isVisible(),true,
        'Invalid link must remain on the page with a recovery message');
      assert.equal(page.url(),base+'/register/');
    }
    const valid=base+'/register/?token=fixture-only&next=/event/123/registrations/';
    await page.locator('#verification-link').fill(valid);
    await page.locator('[data-verification-link-form] button').click();
    await page.waitForURL(valid);
    for(const width of [320,390,760,1440]){
      await page.setViewportSize({width,height:1000});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    }
    const mobile=await browser.newPage({viewport:{width:390,height:844},locale:'zh-CN',
      userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.30'});
    mobile.on('pageerror',error=>errors.push(error.message));
    await mobile.route('**/*',async route=>route.fulfill({response:await route.fetch()}));
    await mobile.route('**/register/**',route=>route.fulfill({status:200,contentType:'text/html',body:fixtures.waiting}));
    await mobile.goto(base+'/register/');
    await mobile.locator('#outdated-browser').waitFor({state:'visible'});
    await mobile.waitForFunction(()=>document.querySelector('#outdated-browser h6')?.textContent==='建议更新浏览器');
    await mobile.waitForFunction(()=>getComputedStyle(document.querySelector('#outdated-browser')).opacity==='1');
    const geometry=await mobile.evaluate(()=>{
      const banner=document.querySelector('#outdated-browser').getBoundingClientRect();
      const heading=document.querySelector('#register-heading').getBoundingClientRect();
      return {height:banner.height,bottom:banner.bottom,heading:heading.top,overflow:document.documentElement.scrollWidth>innerWidth};
    });
    assert.ok(geometry.height<120,'Legacy browser notice stays compact');
    assert.ok(geometry.bottom<geometry.heading,'Notice does not cover registration heading');
    assert.equal(geometry.overflow,false);
    await mobile.screenshot({path:__dirname+'/../output/feedback-1016/registration-waiting-mobile-fixed.png',fullPage:true});
    await mobile.locator('#close-outdated-browser').click();
    await mobile.locator('#outdated-browser').waitFor({state:'hidden'});
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({passed:true,pasted_link_origin_and_target_checked:true,mobile_banner_compact:true,
      browser_errors:errors,real_mail_sent:false}));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});

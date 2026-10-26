const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch();
 try{
  const page=await browser.newPage({locale:'zh-CN',viewport:{width:1440,height:1000}});
  await page.addInitScript(()=>localStorage.setItem('meet-language','zh'));
  await page.goto('http://192.168.2.36:12880/login/');
  const account=JSON.parse(fs.readFileSync(__dirname+'/demo-accounts.json','utf8')).find(a=>a.username==='host-a');
  await page.locator('[name=identifier]').fill(account.username);await page.locator('[name=password]').fill(account.password);
  await Promise.all([page.waitForURL(u=>!u.pathname.startsWith('/login/')),page.locator('#login-form').evaluate(f=>f.requestSubmit())]);
  for(const path of ['/event/4/manage/layout/menu/','/user/profile/','/user/dashboard/?legacy=1']){
   await page.goto('http://192.168.2.36:12880'+path);
   assert.equal(await page.locator('link[href="/portal-assets/native-frame.css"]').count(),1);
   await page.locator(path.includes('/layout/menu/')?'.meet-native-workspace':'.meet-native-workspace[data-native-language=zh]').waitFor();
   if(path.includes('/layout/menu/'))await page.locator('#meet-menu-editor[data-editor-ready]').waitFor();
   for(const width of [320,390,760,1440]){
    await page.setViewportSize({width,height:900});
    if(width===390){
     assert.equal(await page.locator('.meet-frame-mobile-account a[href="/user/profile/"]').isVisible(),true);
     assert.equal(await page.locator('.meet-frame-mobile-account a[href="/user/dashboard/?legacy=1"]').isVisible(),true);
    }
    if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)){
     console.log(JSON.stringify({path,width,overflow:await page.evaluate(()=>[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+2&&getComputedStyle(e).position!=='absolute'&&getComputedStyle(e).position!=='fixed').slice(0,8).map(e=>({tag:e.tagName,class:e.className,width:e.getBoundingClientRect().width})))}));
     assert.fail(`${path} overflow ${width}`);
    }
    if(width===390)await page.screenshot({path:__dirname+`/../output/yujian-native-${path.includes('layout')?'editor':path.includes('profile')?'profile':'records'}-mobile.png`,fullPage:true});
    if(width===1440)await page.screenshot({path:__dirname+`/../output/yujian-native-${path.includes('layout')?'editor':path.includes('profile')?'profile':'records'}-desktop.png`,fullPage:true});
   }
  }
  console.log(JSON.stringify({passed:true,native_skin:true,responsive:[320,390,760,1440]}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

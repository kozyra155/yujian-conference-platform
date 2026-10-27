const projectRoot=require('node:path').resolve(__dirname,'../..');
const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const base='http://192.168.2.36:12880';
async function login(page,username){
 const account=JSON.parse(fs.readFileSync(projectRoot+'/demo-accounts.json','utf8')).find(a=>a.username===username);
 await page.goto(base+'/login/');await page.locator('[name=identifier]').fill(account.username);await page.locator('[name=password]').fill(account.password);
 await Promise.all([page.waitForURL(u=>!u.pathname.startsWith('/login/')),page.locator('#login-form').evaluate(f=>f.requestSubmit())]);
}
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({locale:'zh-CN',viewport:{width:1440,height:1000}});
  await page.addInitScript(()=>localStorage.setItem('meet-language','zh'));
  await login(page,'admin');
  assert.equal((await page.goto(base+'/event/22/manage/layout/menu/')).status(),200);
  await page.locator('#meet-menu-editor[data-editor-ready]').waitFor({timeout:8000});
  assert.equal(await page.locator('#meet-menu-toolbar .el-input').count(),1);
  await page.screenshot({path:projectRoot+'/../output/yujian-editor-22-desktop.png',fullPage:true,animations:'disabled'});
  for(const width of [320,390,760,1440]){
   await page.setViewportSize({width,height:900});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Editor overflow ${width}`);
   if(width===390)await page.screenshot({path:projectRoot+'/../output/yujian-editor-22-mobile.png',fullPage:true,animations:'disabled'});
  }
  console.log(JSON.stringify({passed:true,conference_22_read_only:true,component_toolbar:true,responsive:[320,390,760,1440]}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const fs=require('node:fs');const assert=require('node:assert/strict');
const base='http://192.168.2.36:12880';
(async()=>{
 const browser=await chromium.launch();const errors=[];
 try{
  const page=await browser.newPage({locale:'zh-CN',viewport:{width:1440,height:1000}});
  await page.addInitScript(()=>localStorage.setItem('meet-language','zh'));
  page.on('pageerror',e=>errors.push(e.message));
  const a=JSON.parse(fs.readFileSync(__dirname+'/demo-accounts.json','utf8')).find(a=>a.username==='host-a');
  await page.goto(base+'/login/');await page.locator('[name=identifier]').fill(a.username);await page.locator('[name=password]').fill(a.password);
  await Promise.all([page.waitForURL(u=>!u.pathname.startsWith('/login/')),page.locator('#login-form').evaluate(f=>f.requestSubmit())]);
  for(const [path,name]of [['/user/profile/','profile'],['/user/dashboard/?legacy=1','records']]){
   assert.equal((await page.goto(base+path)).status(),200);await page.locator('.meet-native-workspace[data-native-language=zh]').waitFor();
   if(name==='profile')await page.locator('#personal-details-form-container input').first().waitFor();
   for(const width of [320,390,760,1440]){
    await page.setViewportSize({width,height:900});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${name} overflow ${width}`);
    if(width===390||width===1440)await page.screenshot({path:__dirname+`/../output/yujian-${name}-new-${width===390?'mobile':'desktop'}.png`,fullPage:true,animations:'disabled'});
   }
  }
  await page.goto(base+'/user/profile/');await page.locator('#personal-details-form-container input').first().waitFor();
  const input=page.locator('#personal-details-form-container input[name=first_name]');
  const original=await input.inputValue();await input.fill(original+' draft');
  await page.locator('.language-toggle').click();
  await page.getByRole('heading',{name:'Profile and account settings',exact:true}).waitFor();
  assert.equal(await input.inputValue(),original+' draft');
  await input.fill(original);
  assert.deepEqual(errors,[]);
  const result={passed:true,profile_frame:true,records_frame:true,profile_input_preserved_on_language_change:true,responsive:[320,390,760,1440],browser_errors:errors};
  fs.writeFileSync(__dirname+'/../output/user-frame-verification.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

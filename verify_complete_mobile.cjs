const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage();
    await page.setContent('<body class="complete-site"><div class="header-actions complete-account"><a class="login-link" href="/login/"><span>登录</span></a></div></body>');
    await page.addStyleTag({content:fs.readFileSync('portal/portal.css','utf8')});
    await page.addStyleTag({content:fs.readFileSync('portal/complete-conference.css','utf8')});
    for(const width of [320,390,760]) {
      await page.setViewportSize({width,height:700});
      for(const label of ['登录','Log in']) {
        await page.locator('.login-link>span').evaluate((span,text)=>span.textContent=text,label);
        const span=await page.locator('.login-link>span').boundingBox();
        assert(span.width>10&&span.height>10,`Mobile ${width}px login label must be readable: ${JSON.stringify(span)}`);
      }
    }
    console.log('PASS mobile Chinese/English login labels at 320/390/760px');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});

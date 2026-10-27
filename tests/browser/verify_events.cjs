const projectRoot=require('node:path').resolve(__dirname,'../..');
const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base='http://192.168.2.36:12880';
const fixture=(id,title,start,end)=>({id,title,start,end,timezone:'Asia/Shanghai',location:'武汉',description:'会议介绍 '+id,subject_domains:['人工智能'],organizer_name:'测试主办单位'});
(async()=>{
 const browser=await chromium.launch();
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000},locale:'zh-CN'});const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.addInitScript(()=>localStorage.setItem('meet-language','zh'));
  const actual=await(await page.request.get(base+'/api/conferences/?page=1&q=')).json();
  await page.goto(base+'/events/');await page.locator('.event-card').first().waitFor();
  assert.equal(await page.locator('.event-title').first().innerText(),actual.events[0].title,'Card content must come from published platform meetings');
  assert.equal(await page.locator('.event-card').count(),actual.events.length);assert.equal(await page.locator('[data-public-conferences]').count(),0,'Remove the duplicate plain list');
  assert.doesNotMatch(await page.locator('main').innerText(),/全球杰出科学家基金|本系列场次|约 45 分钟|查看原报名页/);
  for(let i=0;i<actual.events.length;i++)assert.equal(await page.locator('.event-register-link').nth(i).getAttribute('href'),`/event/${actual.events[i].id}/`);
  assert.equal((await page.request.get(base+`/event/${actual.events[0].id}/`)).status(),200);
  assert.equal((await page.request.get(base+'/portal-assets/events-data.json')).status(),404,'Old webinar data must be removed');
  await page.screenshot({path:projectRoot+'/../output/yujian-events-desktop.png',fullPage:true});
  for(const width of [320,390,760,1024,1440]){await page.setViewportSize({width,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${width}px overflow`);if(width===390)await page.screenshot({path:projectRoot+'/../output/yujian-events-mobile.png',fullPage:true});}
  const now=Date.now(),iso=ms=>new Date(ms).toISOString();
  const items=[fixture(900001,'未来会议 <img src=x onerror=alert(1)>',iso(now+86400000),iso(now+172800000)),fixture(900002,'进行中的会议',iso(now-3600000),iso(now+3600000)),fixture(900003,'历史会议',iso(now-172800000),iso(now-86400000))];
  let fail=false,slowResolve;const requests=[];
  await page.route('**/api/conferences/**',async route=>{
   const url=new URL(route.request().url());const q=url.searchParams.get('q')||'';const number=Number(url.searchParams.get('page'));requests.push({q,page:number});
   if(q==='slow')await new Promise(resolve=>{slowResolve=resolve;});
   if(fail)return route.fulfill({status:503,contentType:'application/json',body:'{}'});
   const events=q==='none'?[]:q==='fast'?[items[1]]:number===2?[items[2]]:items;
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({events,page:number,total:q==='none'?0:4,has_more:number===1&&q===''} )});
  });
  await page.goto(base+'/events/');await page.getByText(items[0].title,{exact:true}).waitFor();assert.equal(await page.locator('.event-card img').count(),0,'Titles must be plain text');
  assert.deepEqual(await page.locator('.event-status').allTextContents(),['即将举办','进行中','已结束']);
  await page.getByLabel('显示时区').selectOption('Asia/Shanghai');const sh=await page.locator('.event-local-time').first().innerText();await page.getByLabel('显示时区').selectOption('America/New_York');assert.notEqual(await page.locator('.event-local-time').first().innerText(),sh);
  await page.locator('#events-language').selectOption('en');await page.getByRole('link',{name:'View conference',exact:true}).first().waitFor();assert.deepEqual(await page.locator('.event-status').allTextContents(),['Upcoming','Ongoing','Ended']);assert.equal(await page.locator('.event-title').first().innerText(),items[0].title);
  await page.locator('#events-language').selectOption('zh');await page.getByRole('button',{name:'下一页',exact:true}).click();await page.getByText('历史会议',{exact:true}).waitFor();assert.equal(await page.locator('.event-card').count(),1);await page.getByRole('button',{name:'上一页',exact:true}).click();await page.getByText(items[0].title,{exact:true}).waitFor();
  await page.locator('#events-query').fill('none');await page.locator('#events-empty').waitFor({state:'visible'});assert.equal(await page.locator('.event-card').count(),0);assert.equal(requests.at(-1).page,1);await page.locator('#events-reset').click();await page.getByText(items[0].title,{exact:true}).waitFor();
  const slowRequest=page.waitForRequest(r=>new URL(r.url()).searchParams.get('q')==='slow');await page.locator('#events-query').fill('slow');await slowRequest;await page.locator('#events-query').fill('fast');await page.getByText('进行中的会议',{exact:true}).waitFor();const slowResponse=page.waitForResponse(r=>new URL(r.url()).searchParams.get('q')==='slow');slowResolve();await slowResponse;assert.equal(await page.locator('.event-card').count(),1,'Old search responses must not replace newer results');assert.equal(await page.locator('.event-title').first().innerText(),'进行中的会议');
  fail=true;await page.locator('#events-query').fill('error');await page.locator('#events-error').waitFor({state:'visible'});assert.equal(await page.locator('#events-empty').isVisible(),false);fail=false;await page.locator('#events-retry').click();await page.getByText(items[0].title,{exact:true}).waitFor();assert.equal(await page.locator('#events-error').isVisible(),false);
  assert.deepEqual(errors,[]);const result={passed:true,published_meeting_cards:true,duplicate_list_removed:true,real_detail_links:true,search:true,pagination:true,stale_search_ignored:true,timezones:true,language:true,empty_error_retry:true,mobile:true,browser_errors:errors};fs.writeFileSync(projectRoot+'/events-verification.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

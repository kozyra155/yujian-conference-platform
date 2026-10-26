const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base='http://192.168.2.36:12880';
(async()=>{
 const browser=await chromium.launch();
 try{
  const page=await browser.newPage({locale:'zh-CN',viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.addInitScript(()=>localStorage.setItem('meet-language','zh'));
  await page.goto(base+'/events/');
  assert.equal(await page.locator('#events-filter-time').count(),1,'Time filter must be visible above the cards');
  await page.locator('#events-filter-city option').nth(1).waitFor({state:'attached'});
  const options=await(await page.request.get(base+'/api/conferences/?filters=1')).json();
  assert.equal(await page.locator('#events-filter-subject option').count(),46);
  assert.deepEqual(await page.locator('#events-filter-city option').evaluateAll(nodes=>nodes.slice(1).map(n=>n.value)),options.filters.cities);
  const city=options.filters.cities[0];
  const filtered=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/conferences/'&&new URL(r.url()).searchParams.get('city')===city);
  await page.locator('#events-filter-city').selectOption(city);const actual=await(await filtered).json();await page.waitForFunction(n=>document.querySelectorAll('.event-card').length===n,actual.events.length);assert.ok(actual.events.length>0);
  await page.locator('#events-clear-filters').click();await page.waitForFunction(()=>document.querySelector('#events-filter-city').value==='');
  await page.screenshot({path:__dirname+'/../output/events-filters-desktop.png',fullPage:true});
  for(const width of [320,390,760,1024,1440]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Filters overflow at ${width}`);if(width===390)await page.screenshot({path:__dirname+'/../output/events-filters-mobile.png',fullPage:true});}
  const fixture={id:999001,title:'筛选结果',start:'2030-05-01T01:00:00Z',end:'2030-05-02T01:00:00Z',location:'武汉市',timezone:'Asia/Shanghai',description:'临时筛选结果'};
  let latest;const matches=[];
  await page.route('**/api/conferences/**',async route=>{
   const url=new URL(route.request().url());latest=Object.fromEntries(url.searchParams);matches.push(latest);
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({events:[fixture],page:Number(latest.page),total:25,has_more:Number(latest.page)<3,filters:{months:['2030-05','2029-12'],cities:['武汉市','上海市'],subjects:['人工智能','数学']}})});
  });
  await page.goto(base+'/events/');await page.getByText('筛选结果',{exact:true}).waitFor();const month=page.waitForResponse(r=>new URL(r.url()).searchParams.get('time')==='2030-05');await page.locator('#events-filter-time').selectOption('2030-05');await month;
  const chooseSubject=page.waitForResponse(r=>new URL(r.url()).searchParams.get('subject')==='人工智能');await page.locator('#events-filter-subject').selectOption('人工智能');await chooseSubject;
  const chooseCity=page.waitForResponse(r=>new URL(r.url()).searchParams.get('city')==='武汉市');await page.locator('#events-filter-city').selectOption('武汉市');await chooseCity;
  const search=page.waitForResponse(r=>new URL(r.url()).searchParams.get('q')==='研究');await page.locator('#events-query').fill('研究');await search;assert.equal(latest.time,'2030-05');assert.equal(latest.subject,'人工智能');assert.equal(latest.city,'武汉市');assert.equal(latest.page,'1');
  const next=page.waitForResponse(r=>new URL(r.url()).searchParams.get('page')==='2');await page.getByRole('button',{name:'下一页',exact:true}).click();await next;assert.equal(latest.city,'武汉市');assert.equal(latest.q,'研究');
  const phase=page.waitForResponse(r=>new URL(r.url()).searchParams.get('time')==='ended');await page.locator('#events-filter-time').selectOption('ended');await phase;assert.equal(latest.page,'1','Filter changes reset pagination');
  await page.locator('#events-language').selectOption('en');assert.equal(await page.getByLabel('Conference time filter').count(),1);assert.equal(await page.locator('#events-filter-time').inputValue(),'ended');assert.equal(await page.locator('#events-filter-subject').inputValue(),'人工智能');assert.equal(await page.locator('#events-filter-city').inputValue(),'武汉市');
  const reset=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/conferences/'&&!new URL(r.url()).searchParams.get('city'));await page.locator('#events-clear-filters').click();await reset;assert.equal(latest.page,'1');assert.ok(!latest.city&&!latest.subject&&!latest.time&&!latest.q);assert.equal(await page.locator('#events-query').inputValue(),'');
  assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:true,time_subject_city_filters:true,combined_keyword_query:true,pagination_preserves_filters:true,filter_change_resets_page:true,reset:true,language_preserves_choices:true,mobile:true,browser_errors:errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

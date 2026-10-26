const {chromium}=require('D:/playwright-demo/node_modules/playwright');const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch();try{
 const page=await browser.newPage();await page.goto('http://192.168.2.36:12880/event/61/');
 await page.setContent('<link rel="stylesheet" href="/portal-assets/complete-conference.css"><link rel="stylesheet" href="/portal-assets/appearance-presets.css"><body class="complete-site appearance-simple-1"><section class="complete-side-section"><h2>重要日期</h2></section><time class="complete-news-date"><span>2027.10</span></time></body>',{waitUntil:'networkidle'});
 const colors=['#fa7d4b','#d94a45','#8550ad','#3f67c8','#293d78','#488b35','#ffffff','#ffff00'];
 for(const layout of ['simple-1','simple-2'])for(const accent of colors){
  const ratios=await page.evaluate(({layout,accent})=>{
   document.body.className='complete-site appearance-'+layout;document.body.style.setProperty('--complete-accent',accent);
   const canvas=document.createElement('canvas');canvas.width=canvas.height=1;const ctx=canvas.getContext('2d');
   function luminance(color){ctx.fillStyle=color;ctx.fillRect(0,0,1,1);return [...ctx.getImageData(0,0,1,1).data].slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);}
   return ['.complete-side-section h2','.complete-news-date span'].map(selector=>{const style=getComputedStyle(document.querySelector(selector)),a=luminance(style.color),b=luminance(style.backgroundColor);return{selector,ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)};});
  },{layout,accent});for(const {selector,ratio}of ratios)assert.ok(ratio>=4.5,`${layout} ${accent} ${selector} contrast ${ratio.toFixed(2)} is below 4.5`);
 }
 console.log('PASS readable sidebar headings and date badges in both layouts, six presets plus white/yellow custom accents');
}finally{await browser.close()}})().catch(e=>{console.error(e.message);process.exit(1)});

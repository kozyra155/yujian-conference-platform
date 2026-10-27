const projectRoot=require('node:path').resolve(__dirname,'../..');
const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const base='http://192.168.2.36:12880';
const output=path.resolve(projectRoot,'../output');
function python(code){
 try{return execFileSync('docker',['compose','-p','yujian-indico-v1','exec','-T','indico-web','/opt/indico/.venv/bin/python','-c',code],{cwd:projectRoot,encoding:'utf8'});}
 catch(error){throw new Error('Fixture Python failed: '+String(error.stderr||error.stdout||error.message).trim().slice(-2500));}
}
const cleanup=String.raw`
def cleanup_fixture(event_id,user_ids):
 with app.test_request_context(base_url='http://192.168.2.36:12880'):
  db.session.rollback()
  if event_id:
   event=Event.get(event_id)
   assert event.id not in (22,61) and event.title.startswith('原生业务界面验收 ')
   assert event.creator_id in user_ids
   event.is_deleted=True
  for user_id in user_ids:
   user=User.get(user_id)
   assert user.email.startswith('native-business-') and user.email.endswith('@conference.test')
   user.is_deleted=True
  db.session.commit()
`;
const setup=String.raw`
import atexit,os
os.environ['NATIVE_BUSINESS_PREVIEW']='1'
def cleanup_failed_setup():
 if not globals().get('preview_ready',False) and globals().get('app'):
  cleanup_fixture(globals().get('event_id'),globals().get('user_ids',[]))
atexit.register(cleanup_failed_setup)
`+cleanup+'\n'+fs.readFileSync(path.join(projectRoot,'tests/backend/verify_native_business.py'),'utf8');

(async()=>{
 const browser=await chromium.launch();let fixture;const result={passed:false,pages:[],overflow:[],browser_errors:[],blocked_mutations:[]};
 fs.mkdirSync(output,{recursive:true});
 try{
  fixture=JSON.parse(python(setup).trim().split('\n').at(-1)).preview;
  const contexts={};
  for(const role of ['owner','attendee','reviewer']){
   const context=await browser.newContext({locale:'zh-CN',viewport:{width:1440,height:1000}});
   context.setDefaultTimeout(15000);await context.addCookies(fixture.cookies[role]);
   assert.equal((await context.cookies(base)).length,fixture.cookies[role].length,'Fixture cookies must match the site host');
   await context.addInitScript(()=>localStorage.setItem('meet-language','zh'));
   // The two native POST queries only resolve/list existing objects; all mutations stay in locmem Python.
   await context.route('**/*',route=>{
    const request=route.request(),url=new URL(request.url());
    const nativeQuery=request.method()==='POST' && (url.pathname==='/api/principals' || url.pathname===`/event/${fixture.event_id}/abstracts/other-list`);
    if(['GET','HEAD','OPTIONS'].includes(request.method()) || nativeQuery)return route.continue();
    result.blocked_mutations.push({method:request.method(),path:url.pathname});
    return route.abort('blockedbyclient');
   });
   contexts[role]=context;
  }
  const e=fixture.event_id,f=fixture.form_id,a=fixture.abstract_id,r=fixture.registration_id,t=fixture.track_id;
  const pages=[
   ['registration-overview','owner',`/event/${e}/manage/registration/`],
   ['registration-create','owner',`/event/${e}/manage/registration/create`],
   ['registration-config','owner',`/event/${e}/manage/registration/${f}/`],
   ['registration-edit','owner',`/event/${e}/manage/registration/${f}/edit`],
   ['registration-fields','owner',`/event/${e}/manage/registration/${f}/form/`],
   ['registration-list','owner',`/event/${e}/manage/registration/${f}/registrations/`],
   ['registration-detail','owner',`/event/${e}/manage/registration/${f}/registrations/${r}/`],
   ['abstract-dashboard','owner',`/event/${e}/manage/abstracts/`],
   ['abstract-list','owner',`/event/${e}/manage/abstracts/list/`],
   ['abstract-judgment','owner',`/event/${e}/manage/abstracts/${a}/`],
   ['review-dashboard','reviewer',`/event/${e}/abstracts/reviewing/`],
   ['review-list','reviewer',`/event/${e}/abstracts/reviewing/${t}/`],
   ['review-detail','reviewer',`/event/${e}/abstracts/${a}/`],
   ['public-registration','reviewer',`/event/${e}/registrations/${f}/`],
   ['public-abstracts','attendee',`/event/${e}/abstracts/`]
  ];
  async function capture(page,name){
   for(const width of [1440,390,320]){
    await page.setViewportSize({width,height:1000});await page.waitForTimeout(100);
    if(width<=390 && name==='registration-fields'){
     const buttonWidth=await page.locator('#registration-form-setup-container [class*=picture-selection-btn]').first().evaluate(button=>button.getBoundingClientRect().width);
     assert.equal(buttonWidth>=140,true,'Picture chooser must remain readable on mobile');
    }
    if(width<=390 && name==='abstract-judgment'){
     const textWidth=await page.locator('.abstract-content').evaluate(element=>{const css=getComputedStyle(element);return element.clientWidth-parseFloat(css.paddingLeft)-parseFloat(css.paddingRight)});
     assert.equal(textWidth>=120,true,'Abstract text must remain readable on mobile');
    }
    const measurement=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,offenders:[...document.querySelectorAll('body *')].filter(x=>{const r=x.getBoundingClientRect();return r.width&&r.right>innerWidth+1&&getComputedStyle(x).position!=='fixed'}).slice(0,12).map(x=>({tag:x.tagName,cls:x.className,right:Math.round(x.getBoundingClientRect().right),width:Math.round(x.getBoundingClientRect().width)}))}));
    if(measurement.scroll>width)result.overflow.push({page:name,...measurement});
    await page.screenshot({path:path.join(output,`native-business-${name}-${width}.png`),fullPage:true,animations:'disabled'});
   }
  }
  for(const [name,role,url] of pages){
   const page=await contexts[role].newPage();page.on('pageerror',error=>result.browser_errors.push({page:name,message:error.message}));
   assert.equal((await page.goto(base+url)).status(),200,name);
   await page.locator('.meet-native-business').waitFor();
   assert.equal(await page.locator('.meet-native-workspace').count(),1,name+' single frame');
   if(name==='registration-fields'){
    await page.locator('#registration-form-setup-container .ui').first().waitFor();
    result.react_field_editor=true;
   }
   if(name==='public-registration'){
    await page.locator('#registration-form-submission-container input').first().waitFor();
    assert.equal(await page.locator('#registration-form-submission-container .field.required').count()>=3,true,'React personal fields retain required validation');
    result.react_registration_form=true;
   }
   if(name==='review-detail'){
    const contrast=await page.locator('.review-trigger .i-button').first().evaluate(button=>{
     const rgb=value=>value.match(/[\d.]+/g).slice(0,3).map(Number);
     const luminance=channels=>channels.map(v=>{v/=255;return v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4}).reduce((sum,v,i)=>sum+v*[0.2126,0.7152,0.0722][i],0);
     const foreground=getComputedStyle(button).color;
     let background='rgb(255, 255, 255)';
     for(let element=button;element;element=element.parentElement){const value=getComputedStyle(element).backgroundColor;if(!value.startsWith('rgba')||Number(value.match(/[\d.]+/g)[3])===1){background=value;break;}}
     const values=[luminance(rgb(foreground)),luminance(rgb(background))].sort((a,b)=>b-a);
     return (values[0]+0.05)/(values[1]+0.05);
    });
    assert.equal(contrast>=4.5,true,`Review action contrast must be readable: ${contrast.toFixed(2)}`);
    result.review_action_contrast=true;
   }
   await capture(page,name);result.pages.push(name);
   console.log('Checked '+name);
   if(name==='registration-config'){
    await page.setViewportSize({width:1440,height:1000});
    const trigger=page.locator('.meet-business-content [data-ajax-dialog]:visible').first();
    await trigger.click();await page.locator('.ui-dialog:visible').waitFor();
    await page.locator('.ui-dialog:visible [name=csrf_token]').waitFor({state:'attached'});
    await capture(page,'configuration-dialog');
    assert.equal(await page.locator('.ui-dialog:visible [name=csrf_token]').count()>0,true,'Configuration CSRF preserved');
    result.configuration_dialog=true;
   }
   if(name==='public-abstracts'){
    await page.setViewportSize({width:1440,height:1000});
    const trigger=page.locator('.meet-business-content [data-ajax-dialog]').filter({hasText:/Submit|提交|投稿/}).first();
    await trigger.click();await page.locator('.ui-dialog:visible').waitFor();
    await page.locator('.ui-dialog:visible [name=csrf_token]').waitFor({state:'attached'});
    const dialog=page.locator('.ui-dialog:visible');
    assert.equal(await dialog.locator('.form-label .required').count()>=3,true,'Native submission required markers preserved');
    assert.equal(await dialog.locator('[name=title]').evaluate(input=>input.required && !input.checkValidity()),true,'Native title validation rejects an empty title');
    await dialog.locator('[name=title]').fill('浏览器验收：未提交');
    await dialog.locator('[name=description]').fill('只验证原生编辑和校验，不发送投稿。');
    await capture(page,'submission-dialog');
    assert.equal(await page.locator('.ui-dialog:visible [name=csrf_token]').count()>0,true,'Submission CSRF preserved');
    result.submission_dialog=true;
   }
   await page.close();
  }
  assert.deepEqual(result.overflow,[],'Native pages must not overflow document');
  assert.deepEqual(result.browser_errors,[],'Native page scripts must load');
  assert.deepEqual(result.blocked_mutations,[],'Browser validation must not attempt mutations');
  result.native_validation=true;
  result.passed=true;result.responsive=[1440,390,320];result.mail_backend='memory';
 }finally{
  await browser.close();
  if(fixture)python(`from indico.web.flask.app import make_app\nfrom indico.modules.users import User\nfrom indico.modules.events import Event\nfrom indico.core.db import db\napp=make_app(config_override={'EMAIL_BACKEND':'indico.vendor.django_mail.backends.locmem.EmailBackend','SMTP_USE_CELERY':False})\n${cleanup}\ncleanup_fixture(${fixture.event_id},${JSON.stringify(fixture.user_ids)})`);
  fs.writeFileSync(path.join(output,'native-business-ui.json'),JSON.stringify(result,null,2));
 }
 console.log(JSON.stringify(result));
})().catch(error=>{console.error(error.stack);process.exitCode=1});

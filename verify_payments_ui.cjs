const {chromium}=require('D:/playwright-demo/node_modules/playwright');
const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');
const base='http://192.168.2.36:12880';
function python(code){return execFileSync('docker',['compose','-p','yujian-indico-v1','exec','-T','indico-web','/opt/indico/.venv/bin/python','-c',code],{cwd:__dirname,encoding:'utf8'});}
const common=String.raw`
import json,uuid,os
os.environ['PYTEST_CURRENT_TEST']='verify_payments_ui'
from datetime import timedelta
from decimal import Decimal
from indico.web.flask.app import make_app
from indico.core.db import db
from indico.modules.auth import Identity
from indico.modules.users import User
from indico.modules.users.operations import create_user
from indico.modules.events import Event
from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.payment import payment_event_settings
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration
from indico.modules.events.registration.util import create_personal_data_fields
from indico.util.date_time import now_utc
from yujian_site import YujianSitePlugin
from yujian_site import payments as p
app=make_app(config_override={'EMAIL_BACKEND':'indico.vendor.django_mail.backends.locmem.EmailBackend','SMTP_USE_CELERY':False})
app.config.update(TESTING=True,REPL=True)
`;
const setup=common+String.raw`
import atexit
ready=False
fixtures=[]
event_id=None
def failed_setup():
 if ready:return
 with app.test_request_context():
  db.session.rollback()
  if event_id:
   event=Event.get(event_id)
   assert event.id not in (22,61) and event.title.startswith('收费界面验收 ')
   event.is_deleted=True
  for item in fixtures:
   user=User.get(item['id'])
   assert user.email.startswith('payments-ui-')
   user.is_deleted=True
  db.session.commit()
atexit.register(failed_setup)
with app.test_request_context(base_url='http://192.168.2.36:12880'):
 suffix=uuid.uuid4().hex[:10]
 fixtures=[]
 for role in ('finance','attendee'):
  username='payments-ui-'+role+'-'+suffix
  password=uuid.uuid4().hex+'!Q8'
  user=create_user(username+'@conference.test',{'first_name':'收费界面','last_name':role},Identity(provider='indico',identifier=username,password=password))
  user.is_admin=role=='finance'
  db.session.flush()
  fixtures.append({'id':user.id,'username':username,'password':password})
 db.session.commit()
 owner=app.test_client()
 with owner.session_transaction() as session: session.set_session_user(User.get(fixtures[0]['id']))
 token=json.loads(owner.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']
 created=owner.post('/api/conferences/',json={'title':'收费界面验收 '+suffix,'start':'2027-10-20T09:00','end':'2027-10-22T17:00','location':'武汉','description':'仅供界面验收，禁止实际汇款。','template':'academic-full'},headers={'X-CSRF-Token':token})
 assert created.status_code==201
 event_id=created.json['id']
 event=Event.get(event_id)
 set_feature_enabled(event,'payment',True)
 YujianSitePlugin.event_settings.set(event,'company_collection',True)
 payment_event_settings.set(event,'conditions','TEST ONLY: payment and full refund conditions')
 form=RegistrationForm(event=event,title='普通参会票（验收）',currency='CNY',base_price=100,require_login=True,require_captcha=False,start_dt=now_utc()-timedelta(days=1),end_dt=now_utc()+timedelta(days=2),notification_sender_address='no-reply@example.invalid')
 create_personal_data_fields(form)
 db.session.add(form)
 db.session.commit()
 form_id=form.id
 assert owner.post(f'/api/conferences/{event_id}/publication',json={'published':True},headers={'X-CSRF-Token':token}).status_code==200
 visitor=app.test_client()
 with visitor.session_transaction() as session:session.set_session_user(User.get(fixtures[1]['id']))
 token=json.loads(visitor.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']
 sent=visitor.post(f'/event/{event_id}/registrations/{form_id}/',json={'first_name':'收费界面','last_name':'attendee','email':fixtures[1]['username']+'@conference.test','affiliation':'验收'},headers={'X-CSRF-Token':token})
 assert sent.status_code==200,(sent.status_code,sent.get_data(as_text=True)[:500])
 registration=Registration.query.filter_by(registration_form_id=form_id,user_id=fixtures[1]['id']).one()
 ready=True
 print(json.dumps({'event_id':event_id,'registration_id':registration.id,'form_id':form_id,'users':fixtures}))
`;
(async()=>{
 const browser=await chromium.launch();let fixture;const errors=[];
 try{
  fixture=JSON.parse(python(setup));
  async function context(user){
   const ctx=await browser.newContext({locale:'zh-CN',viewport:{width:1440,height:1000}});ctx.setDefaultTimeout(12000);await ctx.addInitScript(()=>localStorage.setItem('meet-language','zh'));
   const page=await ctx.newPage();page.on('pageerror',error=>errors.push(error.message));
   await page.goto(base+'/login/');await page.locator('[name=identifier]').fill(user.username);await page.locator('[name=password]').fill(user.password);
   await Promise.all([page.waitForURL(url=>url.pathname!=='/login/'),page.locator('#login-form').evaluate(form=>form.requestSubmit())]);
   // No browser action may send a real financial mutation or registration email during UI verification.
   await ctx.route('**/api/**',route=>['POST','PUT','DELETE'].includes(route.request().method())?route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({message:'验收模式：未执行真实财务操作 / Verification only'})}):route.continue());
   return {ctx,page};
  }
  async function screenshots(page,name){
   for(const width of [1440,390,320]){
    await page.setViewportSize({width,height:1000});await page.mouse.move(0,0);
    try{await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);}catch(error){await page.screenshot({path:__dirname+`/../output/payments-overflow-${name}-${width}.png`,fullPage:true});console.error(JSON.stringify(await page.evaluate(()=>[...document.querySelectorAll('body *')].filter(node=>node.getBoundingClientRect().right>innerWidth+1).slice(-20).map(node=>({tag:node.tagName,cls:node.className,right:node.getBoundingClientRect().right})))));throw error;}
    await page.screenshot({path:__dirname+`/../output/payments-${name}-${width}.png`,fullPage:true});
   }
  }
  const finance=await context(fixture.users[0]);
  await finance.page.goto(base+'/company/payments/');await finance.page.locator('.payment-form input[name=account_name]').waitFor();
  assert.equal(await finance.page.getByRole('link',{name:'公司收款配置',exact:true}).count(),1);
  await finance.page.locator('[name=account_name]').fill('遇见科技（界面草稿，未保存）');
  await finance.page.locator('.language-toggle').click();await finance.page.getByRole('heading',{name:'Company bank account',exact:true}).waitFor();
  assert.equal(await finance.page.locator('[name=account_name]').inputValue(),'遇见科技（界面草稿，未保存）');
  await finance.page.locator('.language-toggle').click();await screenshots(finance.page,'company');
  await finance.page.goto(base+`/conference/${fixture.event_id}/payments/`);await finance.page.locator('.payment-order-row').waitFor();
  assert.equal(await finance.page.locator('.payment-fee input').inputValue(),'100.00');
  assert.equal(await finance.page.getByRole('link',{name:'处理订单',exact:true}).count(),1);
  await screenshots(finance.page,'orders');
  const attendee=await context(fixture.users[1]);
  await attendee.page.goto(base+'/participation/');await attendee.page.getByRole('link',{name:'去付款',exact:true}).waitFor();
  assert.equal(await attendee.page.getByRole('link',{name:'公司收款配置',exact:true}).count(),0);
  let paymentPreview='bank';
  await attendee.ctx.route(`**/api/payments/${fixture.registration_id}/`,async route=>{
   const response=await route.fetch();const value=await response.json();
   if(value.order.status==='awaiting'){value.company={account_name:'遇见科技验收账户（禁止汇款）',bank_name:'验收银行（非真实账户）',account_number:'000000000000',contact:'验收联系人'};value.can_pay=true;}
   if(['expired','renewed'].includes(paymentPreview)){
    value.gateways.wechat=true;value.order.terms_accepted_at=new Date().toISOString();
    value.checkout={provider:'wechat',qr:base+'/portal-assets/meet-logo.png',expired:paymentPreview==='expired'};
   }else if(paymentPreview==='exception'){
    value.order.status='payment_exception';value.can_pay=false;
    value.order.payment={provider:'wechat',reference:'UI-EXCEPTION',amount:'100.00',at:new Date().toISOString()};
   }
   await route.fulfill({response,json:value});
  });
  await attendee.page.getByRole('link',{name:'去付款',exact:true}).click();await attendee.page.locator('[name=payer]').waitFor();
  assert.equal(await attendee.page.getByRole('button',{name:'微信扫码支付',exact:true}).count(),0);
  assert.equal(await attendee.page.getByRole('button',{name:'确认已到账',exact:true}).count(),0);
  await attendee.page.locator('[name=payer]').fill('付款草稿');await attendee.page.locator('[name=transfer_reference]').fill('draft-bank-reference');
  await attendee.page.locator('.language-toggle').click();await attendee.page.getByRole('heading',{name:'Choose payment method',exact:true}).waitFor();
  assert.equal(await attendee.page.locator('[name=payer]').inputValue(),'付款草稿');
  await attendee.page.locator('.language-toggle').click();await screenshots(attendee.page,'unpaid');
  await attendee.page.locator('.payment-terms .el-checkbox').click();assert.equal(await attendee.page.locator('input[name=accepted_terms]').isChecked(),true);await attendee.page.getByRole('button',{name:'提交汇款信息，等待核对',exact:true}).click();await attendee.page.locator('[data-test=payment-error]').waitFor();
  assert.match(await attendee.page.locator('[data-test=payment-error]').innerText(),/验收模式/);
  paymentPreview='expired';await attendee.page.reload();
  await attendee.page.getByRole('heading',{name:'选择付款方式',exact:true}).waitFor();
  assert.equal(await attendee.page.locator('.payment-checkout img').count(),0,'Expired QR must be hidden');
  await attendee.ctx.route(`**/api/payments/${fixture.registration_id}/checkout`,async route=>{
   assert.equal(route.request().method(),'POST');assert.equal(route.request().postDataJSON().accepted_terms,true);
   paymentPreview='renewed';await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({provider:'wechat'})});
  });
  await attendee.page.getByRole('button',{name:'微信扫码支付',exact:true}).click();
  await attendee.page.locator('.payment-checkout img').waitFor();
  paymentPreview='exception';await attendee.page.reload();
  await attendee.page.getByRole('button',{name:'提交退款申请',exact:true}).waitFor();
  assert.equal(await attendee.page.locator('[name=invoice_title]').count(),0,'Unreconciled receipts cannot request invoices');
  assert.match(await attendee.page.locator('.el-alert--warning').innerText(),/切勿重复付款/);
  await screenshots(attendee.page,'exception');
  paymentPreview='bank';
  function stage(stage){python(common+`\nwith app.test_request_context(base_url='${base}'):\n from flask import session\n session.set_session_user(User.get(${fixture.users[0].id}))\n reg=Registration.get(${fixture.registration_id})\n assert reg.event_id==${fixture.event_id} and reg.event.title.startswith('收费界面验收 ')\n reg=p.lock_registration(reg)\n order=p.get_order(reg)\n`+(stage==='paid'?` p.confirm_payment(reg,order,'UI-TEST-${fixture.registration_id}',amount='100.00')\n p.apply_invoice(reg,{'kind':'company','title':'界面验收公司','tax_id':'91310000TEST0000000','email':'billing@example.com'})\n`:` p.apply_refund(reg,{'reason':'界面验收退款申请，不实际退款'})\n`)+` db.session.commit()`);}
  stage('paid');await attendee.page.reload();await attendee.page.getByRole('heading',{name:'到账记录',exact:true}).waitFor();
  await screenshots(attendee.page,'paid');
  const receipt=await attendee.ctx.newPage();await receipt.goto(base+`/payments/${fixture.registration_id}/receipt/`);assert.match(await receipt.locator('body').innerText(),/不是税务发票/);
  await receipt.setViewportSize({width:320,height:1000});assert.equal(await receipt.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  stage('refund');await finance.page.goto(base+`/payments/${fixture.registration_id}/`);await finance.page.locator('[name=refund_reference]').waitFor();await screenshots(finance.page,'refund');
  assert.equal(await finance.page.locator('.payment-audit li').count()>0,true);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,company_admin_page:true,fees_and_orders:true,participant_link:true,disabled_gateways_hidden:true,drafts_survive_language_switch:true,payment_receipt:true,refund_finance_form:true,responsive:[320,390,1440],browser_errors:errors,real_money_moved:false,browser_financial_mutations_blocked:true}));
 }finally{
  await browser.close();
  if(fixture)python(common+`\nwith app.test_request_context():\n event=Event.get(${fixture.event_id})\n assert event.id not in (22,61) and event.title.startswith('收费界面验收 ')\n event.is_deleted=True\n for user_id in ${JSON.stringify(fixture.users.map(user=>user.id))}:\n  user=User.get(user_id)\n  assert user.email.startswith('payments-ui-')\n  user.is_deleted=True\n db.session.commit()`);
 }
})().catch(error=>{console.error(error);process.exitCode=1;});

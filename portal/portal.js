(() => {
  function redirectCreation(){
    if(/^#create-event:conference(?::\d+)?$/.test(location.hash))location.replace('/conference/create/');
  }
  window.addEventListener('hashchange',redirectCreation);
  redirectCreation();
  const dictionary=window.MeetTranslations;
  const originals=new WeakMap();
  const attributes=new WeakMap();
  let stored;
  try{stored=localStorage.getItem('meet-language');}catch{}
  let language=stored==='en'?'en':'zh';
  let session=null;
  let pendingSession=null;
  let syncQueue=Promise.resolve();
  let formEdited=false;
  for(const type of ['input','change'])document.addEventListener(type,event=>{
    if(event.target.closest('form,#signup-container'))formEdited=true;
  },true);
  const locale=()=>language==='en'?'en_GB':'zh_Hans_CN';
  function translate(){
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
    let node;
    while((node=walker.nextNode())){
      if(node.parentElement?.closest('script,style,svg,[data-no-translate],#events-grid'))continue;
      if(!originals.has(node))originals.set(node,node.textContent);
      const original=originals.get(node);
      const key=original.trim();
      if(dictionary[key])node.textContent=language==='en'?original.replace(key,dictionary[key]):original;
    }
    document.querySelectorAll('[placeholder],[aria-label],[title],input[type="submit"]').forEach(element=>{
      if(element.closest('[data-no-translate]'))return;
      if(!attributes.has(element))attributes.set(element,new Map());
      const saved=attributes.get(element);
      for(const name of ['placeholder','aria-label','title',...(element.matches('input[type="submit"]')?['value']:[])]){
        if(!element.hasAttribute(name))continue;
        if(!saved.has(name))saved.set(name,element.getAttribute(name));
        const original=saved.get(name);
        if(dictionary[original])element.setAttribute(name,language==='en'?dictionary[original]:original);
      }
    });
    document.querySelectorAll('.language-toggle').forEach(button=>{
      button.textContent=language==='en'?'中文':'EN';
      button.setAttribute('aria-label',language==='en'?'切换到中文':'Switch to English');
      button.title=button.getAttribute('aria-label');
    });
    document.querySelectorAll('[data-zh][data-en]').forEach(element=>element.textContent=language==='en'?element.dataset.en:element.dataset.zh);
    document.documentElement.lang=language==='en'?'en':'zh-CN';
    const path=location.pathname;
    const titles=path.startsWith('/events')?['会议活动 · 遇见科技会议服务平台','Events · Meet Technology Conferences']:path.startsWith('/login')?['登录 · 遇见科技会议服务平台','Log in · Meet Technology Conferences']:path.startsWith('/register')?['注册 · 遇见科技会议服务平台','Register · Meet Technology Conferences']:['遇见科技会议服务平台','Meet Technology Conferences'];
    document.title=document.body.dataset.pageTitle||document.body.dataset.conferenceTitle||titles[language==='en'?1:0];
  }
  function renderAccount(unknown=false){
    const login=document.querySelector('.header-actions .login-link');
    const menu=document.querySelector('.account-menu');
    if(!login||!menu)return;
    const user=session?.user;
    document.querySelectorAll('[data-conference-login]').forEach(element=>element.hidden=!!user);
    document.querySelectorAll('[data-conference-member]').forEach(element=>element.hidden=!user);
    document.querySelectorAll('[data-conference-enroll]').forEach(element=>element.href=user?element.dataset.memberUrl:element.dataset.guestUrl);
    login.hidden=!!user;
    document.querySelectorAll('[data-guest-signup]').forEach(element=>element.hidden=!!user);
    menu.hidden=!user;
    if(user){
      document.querySelectorAll('.account-name,.account-dropdown-name').forEach(element=>element.textContent=user.name);
      document.querySelector('.account-toggle').title=user.name;
    }else{
      menu.open=false;
      document.querySelectorAll('.account-name,.account-dropdown-name').forEach(element=>element.textContent='');
      const label=login.querySelector('span');
      label.textContent=unknown?'账户':'登录';originals.delete(label.firstChild);
      login.href=unknown?'/user/dashboard/':(login.dataset.loginUrl||'/login/');
      login.title=unknown?'无法读取账户状态，点击查看账户':'';
    }
    translate();
  }
  async function refreshSession(){
    if(pendingSession)return pendingSession;
    pendingSession=(async()=>{
      try{
        const response=await fetch('/assets/js-vars/user.js?portal=1',{credentials:'same-origin',cache:'no-store'});
        if(!response.ok)throw new Error('Session unavailable');
        const data=await response.json();
        if(!data.csrf_token||!Object.hasOwn(data,'user')||(data.user&&(!Number.isInteger(data.user.id)||typeof data.user.name!=='string')))throw new Error('Invalid session');
        session=data;renderAccount();return data;
      }catch{session=null;renderAccount(true);return null;}
      finally{pendingSession=null;}
    })();
    return pendingSession;
  }
  function apply(value){
    language=value==='en'?'en':'zh';
    try{localStorage.setItem('meet-language',language);}catch{}
    translate();
    window.dispatchEvent(new CustomEvent('meet-language-change',{detail:{language}}));
  }
  function syncLanguage(reload=false){
    const desired=locale();
    syncQueue=syncQueue.catch(()=>{}).then(async()=>{
      if(desired!==locale())return;
      const data=session||await refreshSession();
      if(!data)return;
      let changed=false;
      if(data.language!==desired){
        const response=await fetch('/change-language',{method:'POST',credentials:'same-origin',headers:{'X-CSRF-Token':data.csrf_token},body:new URLSearchParams({lang:desired})});
        if(!response.ok)throw new Error('Language update failed');
        data.language=desired;
        changed=true;
      }
      const hasDraft=formEdited||[...document.querySelectorAll('form input,form textarea,form select')].some(field=>{
        if(['hidden','submit','button','reset'].includes(field.type))return false;
        if(['checkbox','radio'].includes(field.type))return field.checked!==field.defaultChecked;
        return field.tagName==='SELECT'?field.selectedIndex!==0:field.value!==field.defaultValue;
      });
      if(reload&&changed&&!hasDraft&&desired===locale()&&/^\/(login|register|reset-password)\//.test(location.pathname))location.reload();
      if(desired===locale())window.dispatchEvent(new CustomEvent('meet-language-synced',{detail:{language}}));
    }).catch(()=>{
      let status=document.querySelector('#portal-status');
      if(!status){status=document.createElement('p');status.id='portal-status';status.setAttribute('role','status');document.body.append(status);}
      status.textContent=language==='en'?'The language changed locally. Your account preference could not be saved. Please try again.':'语言已切换，账户语言设置暂未同步，请稍后重试。';
    });
    return syncQueue;
  }
  function setLanguage(value){apply(value);return syncLanguage(true);}
  window.MeetPortal={get language(){return language;},setLanguage,translate,refreshSession};
  document.querySelectorAll('.language-toggle').forEach(button=>button.addEventListener('click',()=>setLanguage(language==='en'?'zh':'en')));
  translate();
  document.addEventListener('DOMContentLoaded',translate);
  refreshSession().then(data=>{
    if(!data)return;
    if(!stored&&data.language.startsWith('en'))apply('en');
    syncLanguage(true);
  });
  window.addEventListener('pageshow',event=>{if(event.persisted)refreshSession();});
  window.addEventListener('focus',refreshSession);
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')refreshSession();});
  document.addEventListener('click',event=>{if(!event.target.closest('.account-menu'))document.querySelectorAll('.account-menu').forEach(menu=>menu.open=false);});
})();

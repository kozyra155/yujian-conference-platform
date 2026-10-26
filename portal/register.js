document.title='注册 · 遇见科技会议服务平台';
if(!document.querySelector('meta[name="viewport"]')){
  const meta=document.createElement('meta');meta.name='viewport';meta.content='width=device-width, initial-scale=1';document.head.append(meta);
}
const form=document.querySelector('#meet-register-email-form');
if(form){
  const translations=new Map([
    ['CAPTCHA','安全验证'],['確認您不是機器人','请完成安全验证'],['Confirm that you are not a robot','请完成安全验证'],
    ['Type the characters you see in the image. You can also listen to the audio instead','输入图片中的字符，也可以播放语音验证码。'],
    ['Hear the characters','播放语音验证码'],['Try different characters','更换验证码'],['回答','验证码'],['Answer','验证码']
  ]);
  function localize(){
    if(window.MeetPortal.language==='en')return;
    const walker=document.createTreeWalker(form,NodeFilter.SHOW_TEXT);
    let node;
    while((node=walker.nextNode())){const replacement=translations.get(node.textContent.trim());if(replacement)node.textContent=replacement;}
    const captcha=form.querySelector('input[name="captcha"]');
    if(captcha&&!captcha.hasAttribute('aria-label')){captcha.setAttribute('aria-label','验证码');captcha.autocomplete='off';}
  }
  localize();
  // The upstream CAPTCHA renders asynchronously; only localize display text in its form.
  new MutationObserver(localize).observe(form,{childList:true,subtree:true});
}
const signup=document.querySelector('#signup-container');
if(signup){
  function brandProfile(){
    const button=signup.querySelector('button[type="submit"]');
    if(button&&['建立我的 Indico 設定檔','Create my Indico profile'].includes(button.textContent.trim())){
      // Preserve React's button and its handlers, changing only the visible text node.
      for(const node of button.childNodes){if(node.nodeType===Node.TEXT_NODE&&node.textContent.includes('Indico'))node.textContent=window.MeetPortal.language==='en'?'Create account':'完成注册';}
    }
  }
  brandProfile();
  new MutationObserver(brandProfile).observe(signup,{childList:true,subtree:true,characterData:true});
}
const recovery=document.querySelector('[data-verification-link-form]');
if(recovery){
  recovery.addEventListener('submit',event=>{
    event.preventDefault();
    const value=recovery.elements.verification_link.value.trim();
    try{
      const link=new URL(value);
      if(link.origin!==location.origin||link.pathname!=='/register/'||link.username||link.password||link.hash||
         /[\\\s]/.test(value)||!link.searchParams.get('token')||
         [...link.searchParams.keys()].some(key=>!['token','next'].includes(key)||link.searchParams.getAll(key).length!==1))throw new Error();
      const target=link.searchParams.get('next');
      if(target){
        const relative=target.startsWith(location.origin+'/')?target.slice(location.origin.length):target;
        const path=relative.split(/[?#]/)[0];
        const match=path.match(/^\/event\/([1-9]\d*)\/(?:(?:registrations|abstracts|page|overview|interest)(?:\/[A-Za-z0-9_-]+)*\/?)?$/);
        if(/[\\\s]/.test(target)||!match||Number(match[1])>2147483647)throw new Error();
      }
      location.assign(link.href);
    }catch{
      recovery.querySelector('[data-verification-link-error]').hidden=false;
    }
  });
}
const browserNotice=document.querySelector('#outdated-browser');
if(browserNotice){
  document.body.prepend(browserNotice);
  function localizeBrowserNotice(){
    const english=window.MeetPortal?.language==='en';
    const heading=browserNotice.querySelector('h6');
    const description=browserNotice.querySelector('p:not(.last)');
    const close=browserNotice.querySelector('#close-outdated-browser');
    for(const [node,value] of [[heading,english?'Browser update recommended':'建议更新浏览器'],
      [description,english?'If registration does not work, update your browser or open this link in Safari or Chrome.':'若无法完成注册，请更新浏览器，或在 Safari、Chrome 中打开邮件链接。']]){
      if(node&&node.textContent!==value)node.textContent=value;
    }
    if(close){close.title=english?'Close':'关闭';close.setAttribute('aria-label',close.title);}
  }
  browserNotice.setAttribute('data-no-translate','');
  new MutationObserver(localizeBrowserNotice).observe(browserNotice,{childList:true,subtree:true});
  window.addEventListener('meet-language-change',localizeBrowserNotice);
  localizeBrowserNotice();
}

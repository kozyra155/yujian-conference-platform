(() => {
 const header=document.querySelector('.page-header');
 if(!header)return;
 const english=document.documentElement.lang.startsWith('en');
 const event=location.pathname.match(/^\/event\/(\d+)\/manage\//);
 const bar=document.createElement('div');bar.className='native-workspace-bar';
 const back=document.createElement('a');back.href=event?`/conference/${event[1]}/`:'/user/dashboard/';
 back.textContent=event?(english?'← Website workspace':'← 返回网站工作台'):(english?'← My conferences':'← 返回我的会议');
 bar.append(back);
 const menu=document.querySelector('.side-menu');
 if(menu){
  const column=menu.closest('.menu-column');
  column.id='native-navigation';
  const button=document.createElement('button');button.type='button';button.className='native-menu-toggle';
  button.textContent=english?'Navigation':'功能导航';button.setAttribute('aria-controls',column.id);button.setAttribute('aria-expanded','false');
  button.addEventListener('click',()=>{const open=document.body.classList.toggle('native-menu-open');button.setAttribute('aria-expanded',String(open));});
  bar.append(button);
 }
 header.insertAdjacentElement('afterend',bar);
})();

(() => {
 const frame=document.querySelector('.meet-native-workspace');
 if(!frame)return;
 function updateTitle(language){
  document.body.dataset.pageTitle=frame.querySelector('h1')?.textContent+' · '+(language==='en'?'Meet Technology':'遇见科技');
  document.title=document.body.dataset.pageTitle;
 }
 updateTitle(window.MeetPortal?.language||'zh');
 const accountTabs=frame.querySelector('.meet-profile-tabs');
 if(accountTabs){
  const advanced=[...accountTabs.querySelectorAll('a')].filter(link=>['/user/applications/','/user/tokens/','/user/api/','/user/data-export'].includes(new URL(link.href).pathname)).map(link=>link.closest('li'));
  if(advanced.length){
   const more=document.createElement('details');more.className='meet-profile-more';
   const summary=document.createElement('summary');summary.dataset.zh='更多设置';summary.dataset.en='More settings';summary.textContent=window.MeetPortal?.language==='en'?'More settings':'更多设置';
   const list=document.createElement('ul');advanced.forEach(item=>list.append(item));more.append(summary,list);accountTabs.append(more);
   more.open=advanced.some(item=>item.classList.contains('active'));
  }
 }
 let edited=false;
 frame.addEventListener('input',()=>edited=true);
 frame.addEventListener('change',event=>{if(event.target.closest('form'))edited=true;});
 window.addEventListener('meet-language-change',event=>{
  updateTitle(event.detail.language);
 });
 window.addEventListener('meet-language-synced',event=>{
  if(frame.dataset.active==='editor')return;
  // Reload native React labels only when there is no user input or open dialog to lose.
  if(!edited&&!document.querySelector('.ui-dialog')&&event.detail.language!==frame.dataset.nativeLanguage){
   location.reload();
  }
 });
})();

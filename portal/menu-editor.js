(() => {
 const root=document.querySelector('#meet-menu-editor');
 if(!root)return;
 let category='website',query='',sorting=false,scheduled=false;
 const locked=root.dataset.locked==='true';
 const t=(zh,en)=>window.MeetPortal?.language==='en'?en:zh;
 const observer=new MutationObserver(()=>schedule());
 function setText(element,value){if(element&&element.textContent!==value)element.textContent=value;}
 function kind(entry){
  if(String(entry.dataset.entryId)===root.dataset.overviewId)return 'home';
  if(entry.querySelector(':scope > .i-label > .entry-page'))return 'page';
  if(entry.querySelector(':scope > .i-label > .entry-user_link'))return 'link';
  if(entry.querySelector(':scope > .i-label > .entry-separator'))return 'separator';
  return 'function';
 }
 function enhance(entry){
  const type=kind(entry),label=entry.querySelector(':scope > .i-label');
  if(!label)return;
  entry.dataset.meetKind=type;
  if(!label.querySelector('.meet-drag-grip')){
   const grip=document.createElement('span');grip.className='meet-drag-grip';grip.textContent='⠿';grip.setAttribute('aria-hidden','true');label.prepend(grip);
  }
  let badge=label.querySelector('.meet-entry-kind');
  if(!badge){badge=document.createElement('span');badge.className='meet-entry-kind';label.querySelector('.title').after(badge);}
  setText(badge,type==='page'?t('内容页面','Page'):type==='link'?t('外部链接','Link'):type==='home'?t('会议首页','Home'):type==='separator'?t('分隔线','Separator'):t('会务功能','Tool'));
  const edit=label.querySelector('.edit-entry');
  setText(edit,type==='page'?t('编辑内容','Edit content'):type==='link'?t('编辑链接','Edit link'):t('设置','Settings'));
  edit?.setAttribute('aria-label',edit.textContent);
  const visibility=label.querySelector('.enabled,.not-enabled');
  if(visibility){const shown=visibility.classList.contains('enabled');setText(visibility,shown?t('导航显示','Shown'):t('已隐藏','Hidden'));visibility.setAttribute('aria-label',shown?t('从导航隐藏','Hide from navigation'):t('显示在导航','Show in navigation'));}
  const home=label.querySelector('.default,.not-default');
  if(home){setText(home,home.classList.contains('default')?t('首页','Home'):'');home.setAttribute('aria-label',home.classList.contains('default')?t('取消默认首页','Unset default home'):t('设为默认首页','Set as default home'));}
  const remove=label.querySelector('.delete-entry');remove?.setAttribute('aria-label',t('删除栏目','Delete section'));
  if(locked)label.querySelector('.actions')?.setAttribute('hidden','');
 }
 function refresh(){
  const list=root.querySelector('#menu-entries > .menu-entries');
  if(!list||sorting)return;
  observer.disconnect();
  const entries=[...list.querySelectorAll('.menu-entry')];entries.forEach(enhance);
  const counts={website:0,functions:0,all:entries.length,matched:0};
  entries.forEach(entry=>counts[['home','page','link','separator'].includes(entry.dataset.meetKind)?'website':'functions']++);
  function filterList(ul){
   let hasMatch=false;
   for(const li of ul.children){
    const entry=li.querySelector(':scope > .menu-entry');if(!entry)continue;
    const child=entry.querySelector(':scope > .menu-entries');
    const childMatch=child?filterList(child):false;
    const website=entry.dataset.meetKind!=='function';
    const match=(category==='all'||website===(category==='website'))&&entry.querySelector(':scope > .i-label > .title').textContent.toLocaleLowerCase().includes(query);
    li.hidden=!(match||childMatch);if(!li.hidden)hasMatch=true;
   }
   return hasMatch;
  }
  filterList(list);
  counts.matched=entries.filter(entry=>!entry.closest('li[hidden]')).length;
  root.querySelector('.meet-editor-empty').hidden=counts.matched>0;
  const canSort=category==='all'&&!query&&!locked;
  root.classList.toggle('meet-can-sort',canSort);
  window.jQuery?.(root).find('.menu-entries.ui-sortable').sortable('option','disabled',!canSort);
  root.setAttribute('data-editor-ready','');
  window.dispatchEvent(new CustomEvent('meet-menu-counts',{detail:counts}));
  observer.observe(list,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});
 }
 function schedule(){if(scheduled||sorting)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;refresh();});}
 window.addEventListener('meet-menu-filter',event=>{category=event.detail.category;query=event.detail.query.trim().toLocaleLowerCase();schedule();});
 window.addEventListener('meet-language-change',schedule);
 window.jQuery(()=>{
  root.querySelector('#meet-editor-enable')?.addEventListener('click',()=>root.querySelector('#toggle-menu-customization')?.click());
  const advanced=root.querySelector('#menu-customization > .row:first-child');
  if(advanced){
   const details=document.createElement('details');details.className='meet-editor-advanced';
   const summary=document.createElement('summary');summary.dataset.zh='高级设置';summary.dataset.en='Advanced settings';summary.textContent=t('高级设置','Advanced settings');details.append(summary,advanced);root.querySelector('#meet-editor-advanced-slot').append(details);
  }
  window.jQuery(document).on('sortstart.meetEditor','#menu-entries .menu-entries',()=>sorting=true).on('sortstop.meetEditor','#menu-entries .menu-entries',()=>{sorting=false;schedule();});
  // Observe the container too: native deletion replaces the entire root list.
  new MutationObserver(schedule).observe(root.querySelector('#menu-entries')||root,{childList:true});
  if(root.dataset.enabled==='false')root.setAttribute('data-editor-ready','');
  refresh();
 });
})();

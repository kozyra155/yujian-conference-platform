(() => {
  const targets=[...document.querySelectorAll('[data-public-conferences]')];
  if(!targets.length)return;
  const t=(zh,en)=>window.MeetPortal.language==='en'?en:zh;
  let events=[],page=1,total=0,hasMore=false,query='',failed=false,loading=false;
  let latestRequest=0;
  const search=document.querySelector('.conference-search');
  function render(){
    for(const target of targets){
      target.replaceChildren();
      for(const event of events){
        const item=document.createElement('article');item.className='conference-row';
        const details=document.createElement('div');details.className='conference-main';
        const heading=document.createElement('h3'),title=document.createElement('a');title.href=`/event/${event.id}/`;title.textContent=event.title;heading.append(title);
        const meta=document.createElement('p');meta.className='conference-meta';
        const date=value=>new Intl.DateTimeFormat(window.MeetPortal.language==='en'?'en-GB':'zh-CN',{timeZone:event.timezone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));
        meta.textContent=`${date(event.start)} – ${date(event.end)} · ${event.location||t('地点待定','Location to be announced')}`;
        const link=document.createElement('a');link.className='meeting-link';link.href=title.href;link.textContent=t('查看会议 ›','View conference ›');
        details.append(heading,meta);item.append(details,link);target.append(item);
      }
      if(!events.length&&(loading||failed||!document.querySelector('#no-results'))){const note=document.createElement('p');note.className='empty-state';note.textContent=loading?t('正在加载会议…','Loading conferences…'):failed?t('会议加载失败，请刷新重试。','Could not load conferences. Please refresh.'):t('暂无符合条件的公开会议。','No matching public conferences.');target.append(note);}
    }
    const status=document.querySelector('#search-status');if(status)status.textContent=t(`找到 ${total} 场会议`,`${total} conferences found`);
    const empty=document.querySelector('#no-results');if(empty)empty.hidden=loading||failed||events.length>0;
    document.querySelectorAll('.public-conference-pages').forEach(el=>el.remove());
    if(page>1||hasMore){
      const nav=document.createElement('div');nav.className='public-conference-pages';
      for(const [label,value,disabled] of [[t('上一页','Previous'),page-1,page===1],[t('下一页','Next'),page+1,!hasMore]]){
        const button=document.createElement('button');button.type='button';button.className='button button-outline';button.textContent=label;button.disabled=disabled||loading;button.onclick=()=>load(value);nav.append(button);
      }
      targets[0].after(nav);
    }
  }
  async function load(value=1){
    const requestId=++latestRequest;loading=true;failed=false;render();
    try{
      const res=await fetch(`/api/conferences/?${new URLSearchParams({page:value,q:query})}`,{cache:'no-store'});
      if(!res.ok)throw new Error();
      const result=await res.json();
      if(!Array.isArray(result.events))throw new Error();
      if(requestId!==latestRequest)return;
      events=result.events;page=result.page;total=result.total;hasMore=result.has_more;
    }catch{if(requestId!==latestRequest)return;failed=true;events=[];total=0;hasMore=false;}
    if(requestId===latestRequest){loading=false;render();}
  }
  search?.addEventListener('submit',event=>{event.preventDefault();query=document.querySelector('#conference-query').value.trim();load(1);});
  window.addEventListener('meet-language-change',render);
  load();
})();

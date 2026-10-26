const grid=document.querySelector('#events-grid');
const query=document.querySelector('#events-query');
const timezone=document.querySelector('#events-timezone');
const language=document.querySelector('#events-language');
const template=document.querySelector('#event-card-template');
const timeFilter=document.querySelector('#events-filter-time');
const subjectFilter=document.querySelector('#events-filter-subject');
const cityFilter=document.querySelector('#events-filter-city');
const t=(zh,en)=>window.MeetPortal.language==='en'?en:zh;
let events=[],page=1,total=0,hasMore=false,loading=false,failed=false,latestRequest=0,searchTimer;
let filterOptions=null,filterLabels='';
function selection(){return {q:query.value.trim(),time:timeFilter.value,subject:subjectFilter.value,city:cityFilter.value};}
function renderFilters(){
 const labels=JSON.stringify([window.MeetPortal.language,filterOptions]);
 if(labels===filterLabels)return;filterLabels=labels;
 function options(select,items){
  const value=select.value;
  select.replaceChildren(...items.map(([key,label])=>{const option=document.createElement('option');option.value=key;option.textContent=label;return option;}));
  select.value=value;
 }
 options(timeFilter,[['',t('全部时间','All dates')],['upcoming',t('即将举办','Upcoming')],['ongoing',t('进行中','Ongoing')],['ended',t('已结束','Ended')],...(filterOptions?.months||[]).map(month=>[month,t(month.slice(0,4)+'年'+month.slice(5)+'月',month)])]);
 options(subjectFilter,[['',t('全部学科','All subjects')],...(filterOptions?.subjects||[]).map(subject=>[subject,subject])]);
 options(cityFilter,[['',t('全部城市','All cities')],...(filterOptions?.cities||[]).map(city=>[city,city])]);
 timeFilter.setAttribute('aria-label',t('会议时间筛选','Conference time filter'));subjectFilter.setAttribute('aria-label',t('会议学科筛选','Conference subject filter'));cityFilter.setAttribute('aria-label',t('会议城市筛选','Conference city filter'));
}
function render(){
 renderFilters();
 language.value=window.MeetPortal.language;
 const en=language.value==='en',locale=en?'en-GB':'zh-CN';
 const zone=timezone.value==='auto'?Intl.DateTimeFormat().resolvedOptions().timeZone:timezone.value;
 const format=new Intl.DateTimeFormat(locale,{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
 const chinaFormat=new Intl.DateTimeFormat(locale,{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
 const fragment=document.createDocumentFragment();
 for(const event of events){
  const card=template.content.cloneNode(true),start=new Date(event.start),end=new Date(event.end);
  const text=(selector,value)=>{card.querySelector(selector).textContent=value;};
  const phase=Date.now()<start.getTime()?'upcoming':Date.now()<end.getTime()?'ongoing':'ended';
  text('.event-topic',event.subject_domains?.[0]||t('学术会议','Conference'));
  text('.event-status',{upcoming:t('即将举办','Upcoming'),ongoing:t('进行中','Ongoing'),ended:t('已结束','Ended')}[phase]);
  card.querySelector('.event-status').dataset.phase=phase;
  text('.event-title',event.title);
  text('.event-subtitle',event.description||'');card.querySelector('.event-subtitle').hidden=!event.description;
  text('.event-time-label',t('会议时间','Conference dates'));
  text('.event-local-time',`${format.format(start)} – ${format.format(end)}`);card.querySelector('time').dateTime=event.start;
  text('.event-zone',zone);
  text('.event-china-time',t('中国时间：','China time: ')+`${chinaFormat.format(start)} – ${chinaFormat.format(end)}`);
  card.querySelector('.event-china-time').hidden=zone==='Asia/Shanghai';
  text('.event-region',t('会议地点：','Location: ')+(event.location||t('地点待定','To be announced')));
  text('.event-footnote',event.organizer_name?t('主办方：','Organizer: ')+event.organizer_name:t('会议内容由主办方维护','Details maintained by the organizer'));
  const link=card.querySelector('.event-register-link');link.href=`/event/${event.id}/`;link.textContent=t('查看会议','View conference');
  fragment.append(card);
 }
 grid.replaceChildren(fragment);grid.setAttribute('aria-busy',String(loading));
 document.querySelector('#events-empty').hidden=loading||failed||events.length>0;
 document.querySelector('#events-error').hidden=!failed;
 document.querySelector('#events-count').textContent=loading?t('正在加载会议…','Loading conferences…'):failed?t('会议列表加载失败','Could not load conferences'):t(`共 ${total} 场会议`,`${total} conferences`);
 const pagination=document.querySelector('#events-pagination');pagination.hidden=failed||!(page>1||hasMore);
 document.querySelector('#events-prev').disabled=loading||page===1;document.querySelector('#events-next').disabled=loading||!hasMore;
 document.querySelector('#events-page-number').textContent=t(`第 ${page} 页`,`Page ${page}`);
 document.querySelectorAll('[data-zh][data-en]').forEach(el=>el.textContent=en?el.dataset.en:el.dataset.zh);
 query.placeholder=t('搜索会议名称或地点','Search conference titles or locations');query.setAttribute('aria-label',query.placeholder);
 document.documentElement.lang=en?'en':'zh-CN';
}
async function load(value=1){
 clearTimeout(searchTimer);
 const requestId=++latestRequest,filters=selection(),selectionKey=JSON.stringify(filters);loading=true;failed=false;events=[];render();
 try{
  const response=await fetch(`/api/conferences/?${new URLSearchParams({page:value,...filters,...(!filterOptions?{filters:'1'}:{})})}`,{cache:'no-store'});
  if(!response.ok)throw new Error('Conference request failed');
  const result=await response.json();
  if(!Array.isArray(result.events)||!Number.isInteger(result.page)||result.page<1||!Number.isInteger(result.total)||result.total<0||typeof result.has_more!=='boolean'||result.events.some(event=>!Number.isInteger(event.id)||event.id<1||typeof event.title!=='string'||Number.isNaN(Date.parse(event.start))||Number.isNaN(Date.parse(event.end))))throw new Error('Invalid conference data');
  if(requestId!==latestRequest||selectionKey!==JSON.stringify(selection()))return;
  if(result.filters){if(!['months','subjects','cities'].every(key=>Array.isArray(result.filters[key])&&result.filters[key].every(item=>typeof item==='string')))throw new Error('Invalid filter choices');filterOptions=result.filters;}
  events=result.events;page=result.page;total=result.total;hasMore=result.has_more;
 }catch{
  if(requestId!==latestRequest||selectionKey!==JSON.stringify(selection()))return;
  failed=true;events=[];total=0;hasMore=false;
 }
 if(requestId===latestRequest){loading=false;render();}
}
query.addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>load(1),250);});
document.querySelector('.events-search-row').addEventListener('submit',event=>{event.preventDefault();load(1);});
timezone.addEventListener('change',render);
language.addEventListener('change',()=>window.MeetPortal.setLanguage(language.value));
window.addEventListener('meet-language-change',render);
function resetFilters(){query.value='';timeFilter.value='';subjectFilter.value='';cityFilter.value='';load(1);}
for(const select of [timeFilter,subjectFilter,cityFilter])select.addEventListener('change',()=>load(1));
document.querySelector('#events-reset').addEventListener('click',resetFilters);
document.querySelector('#events-clear-filters').addEventListener('click',resetFilters);
document.querySelector('#events-retry').addEventListener('click',()=>load(page));
document.querySelector('#events-prev').addEventListener('click',()=>load(page-1));
document.querySelector('#events-next').addEventListener('click',()=>load(page+1));
load();

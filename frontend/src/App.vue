<script setup>
import {ref,computed,onMounted,onUnmounted,nextTick} from 'vue';
import {ElConfigProvider,ElButton,ElIcon,ElInput,ElSelect,ElOption,ElTag,ElTable,ElTableColumn,ElEmpty,ElPagination,ElForm,ElFormItem,ElDatePicker,ElRadioGroup,ElRadioButton,ElSteps,ElStep,ElTabs,ElTabPane,ElAlert,ElSkeleton,ElMessage,ElMessageBox} from 'element-plus';
import {Grid,Calendar,Plus,Search,ArrowRight,Location,Monitor,Document,Setting,View,Link,Check,User,Back,Promotion,Clock,Collection,Refresh,InfoFilled as InfoIcon} from '@element-plus/icons-vue';
import zhCn from 'element-plus/es/locale/lang/zh-cn';
import en from 'element-plus/es/locale/lang/en';
import SiteContentEditor from './SiteContentEditor.vue';
import BusinessWorkspace from './BusinessWorkspace.vue';
import PaymentWorkspace from './PaymentWorkspace.vue';
import BasicConferenceEditor from './BasicConferenceEditor.vue';
import ConferenceMetadataFields from './ConferenceMetadataFields.vue';
import {errorMessage} from './apiErrors.js';

const props=defineProps({mode:String,eventId:Number,financeAdmin:Boolean});
const language=ref(window.MeetPortal?.language||localStorage.getItem('meet-language')||'zh');
const t=(zh,en)=>language.value==='en'?en:zh;
const locale=computed(()=>language.value==='en'?en:zhCn);
const requestedTab=new URLSearchParams(location.search).get('tab');
const events=ref([]),loading=ref(true),error=ref(''),keyword=ref(''),filter=ref('all'),page=ref(1),total=ref(0),busy=ref(false),user=ref(null),tab=ref(['design','content','settings'].includes(requestedTab)?requestedTab:'overview');
const form=ref({title:'',start:'',end:'',organizer_name:'',organizer_phone:'',country:'中国',province:'',city:'',detail_address:'',subject_domains:[],planned_indexing:[],description:'',template:'academic-full'});
const formRef=ref(),siteEditor=ref();
let latestRequest=0;
const website=computed(()=>events.value.find(e=>e.id===props.eventId));
const websiteUrl=computed(()=>website.value?new URL(website.value.url,location.origin).href:'');
const filtered=computed(()=>events.value.filter(e=>(filter.value==='all'||e.published===(filter.value==='published'))&&`${e.title} ${e.location}`.toLocaleLowerCase().includes(keyword.value.trim().toLocaleLowerCase())));
const published=computed(()=>events.value.filter(e=>e.published).length);
const upcoming=computed(()=>events.value.filter(e=>new Date(e.end)>new Date()).length);
const heading=computed(()=>props.mode==='company-payments'?t('公司收款配置','Company collection settings'):props.mode==='payments'?t('收费与订单','Fees & orders'):props.mode==='payment-detail'?t('会议付款订单','Conference payment order'):props.mode==='operations'?t('办会管理','Conference operations'):props.mode==='participation'?t('我的参会','My participation'):props.mode==='directory'?t('发现学术会议','Discover conferences'):props.mode==='create'?t('创建会议网站','Create a conference website'):props.mode==='website'?t('网站工作台','Website workspace'):t('我的会议','My conferences'));
const date=value=>new Intl.DateTimeFormat(language.value==='en'?'en-GB':'zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));
const initials=computed(()=>user.value?.name?.slice(0,1)||'M');
const rules=computed(()=>({title:[{required:true,whitespace:true,message:t('请输入会议名称','Enter a conference title'),trigger:'blur'}],start:[{required:true,message:t('请选择开始时间','Choose a start time'),trigger:'change'}],end:[{required:true,message:t('请选择结束时间','Choose an end time'),trigger:'change'}],description:[{required:true,whitespace:true,message:t('请填写会议简介','Add a conference introduction'),trigger:'blur'}]}));
const phaseLabel=event=>({upcoming:t('即将举办','Upcoming'),ongoing:t('进行中','Ongoing'),ended:t('已结束','Ended')}[event.phase||(Date.now()<new Date(event.start)?'upcoming':Date.now()<new Date(event.end)?'ongoing':'ended')]);

async function request(url,options={}){
 const session=options.method?await window.MeetPortal.refreshSession():null;
 if(options.method&&!session?.user)throw new Error(t('登录状态已失效，请重新登录后操作。','Your session expired. Please log in again.'));
 const response=await fetch(url,{credentials:'same-origin',cache:'no-store',...options,headers:{'Content-Type':'application/json',...(session?{'X-CSRF-Token':session.csrf_token}:{}),...options.headers}});
 if(!response.ok){let data;try{data=await response.json();}catch{}throw new Error(response.status===403?t('您没有操作权限，或会议已锁定。','Permission denied, or the conference is locked.'):response.status===401?t('请先登录。','Please log in.'):errorMessage(data,t('操作未完成，请检查填写的信息后重试。','The operation failed. Check the details and try again.')));}
 return response.json();
}
async function load(){
 if(['operations','participation','payments','company-payments','payment-detail'].includes(props.mode)){loading.value=false;return;}
 const version=++latestRequest;
 loading.value=true;error.value='';
 try{
  if(props.mode==='directory'){
   const result=await request(`/api/conferences/?page=${page.value}&q=${encodeURIComponent(keyword.value.trim())}`);
   if(version!==latestRequest)return;
   events.value=result.events;total.value=result.total;
  }else if(props.mode!=='create'){
   const result=await request('/api/organizer/conferences/');
   if(version!==latestRequest)return;
   events.value=result.events;
  }
  if(props.mode==='website'&&!website.value)error.value=t('未找到您可以管理的会议。','No manageable conference was found.');
 }catch(e){if(version===latestRequest)error.value=e.message;}finally{if(version===latestRequest)loading.value=false;}
}
async function search(){page.value=1;await load();}
async function create(){
 if(busy.value||!await formRef.value.validate().catch(()=>false))return;
 if(new Date(form.value.end)<=new Date(form.value.start)){ElMessage.error(t('结束时间必须晚于开始时间。','End time must be after start time.'));return;}
 if(!form.value.title.trim()||!form.value.description.trim()){ElMessage.error(t('请填写完整的会议信息。','Complete the conference details.'));return;}
 busy.value=true;error.value='';
 try{const event=await request('/api/conferences/',{method:'POST',body:JSON.stringify(form.value)});location.assign(event.builder_url);}catch(e){error.value=e.message;busy.value=false;}
}
async function publish(){
 if(busy.value||!website.value)return;
 const value=!website.value.published;
 try{await ElMessageBox.confirm(value?t('发布后，所有人都可以访问会议网站，会议也会出现在公开列表中。','Publishing makes the website accessible to everyone and adds it to the public directory.'):t('撤回后，只有本会议管理者可以访问网站，会议将从公开列表中移除。','Withdrawing limits access to conference managers and removes the website from the public directory.'),value?t('发布会议网站','Publish conference website'):t('撤回会议网站','Withdraw conference website'),{confirmButtonText:value?t('确认发布','Publish'):t('确认撤回','Withdraw'),cancelButtonText:t('取消','Cancel'),type:value?'info':'warning'});}catch{return;}
 busy.value=true;error.value='';
 try{const event=await request(`/api/conferences/${props.eventId}/publication`,{method:'POST',body:JSON.stringify({published:value})});events.value=events.value.map(e=>e.id===event.id?event:e);ElMessage.success(value?t('会议网站已发布','Website published'):t('会议网站已撤回','Website withdrawn'));}catch(e){error.value=e.message;}finally{busy.value=false;}
}
async function copy(){
 try{await navigator.clipboard.writeText(new URL(website.value.url,location.origin).href);ElMessage.success(t('网址已复制','Link copied'));}catch{ElMessage.warning(t('请选中下方网址手动复制。','Select the address below and copy it manually.'));}
}
async function openAppearance(){tab.value='design';await nextTick();document.getElementById('appearance-presets')?.scrollIntoView({block:'start'});}
async function openBasic(){tab.value='settings';await nextTick();document.getElementById('conference-basic')?.scrollIntoView({block:'start'});}
function basicSaved(event){events.value=events.value.map(item=>item.id===event.id?event:item);}
function changeLanguage(event){language.value=event.detail.language;}
onMounted(async()=>{
 window.addEventListener('meet-language-change',changeLanguage);
 const session=await window.MeetPortal.refreshSession();user.value=session?.user;language.value=window.MeetPortal.language;
 await load();
});
onUnmounted(()=>window.removeEventListener('meet-language-change',changeLanguage));
</script>

<template>
 <ElConfigProvider :locale="locale">
  <div class="workspace" :data-workspace-ready="loading?null:''">
   <aside class="workspace-sidebar" :class="{'workspace-finance-navigation':financeAdmin}" :aria-label="t('会议工作台导航','Workspace navigation')">
    <a class="workspace-brand" href="/organizer/"><span class="brand-mark"><ElIcon><Collection/></ElIcon></span><span>{{t('会议工作台','Conference workspace')}}<small>Meet Technology</small></span></a>
    <p class="nav-group">{{t('会议服务','Conference services')}}</p>
    <nav>
     <a href="/user/dashboard/" :class="{selected:mode==='organizer'||mode==='website'||mode==='operations'}"><ElIcon><Grid/></ElIcon>{{t('我的会议','My conferences')}}</a>
     <a href="/conference/create/" :class="{selected:mode==='create'}"><ElIcon><Plus/></ElIcon>{{t('创建会议','Create conference')}}</a>
     <a href="/category/1/" :class="{selected:mode==='directory'}"><ElIcon><Calendar/></ElIcon>{{t('会议目录','Conference directory')}}</a>
     <a v-if="financeAdmin" href="/company/payments/" :class="{selected:mode==='company-payments'}"><ElIcon><Setting/></ElIcon>{{t('公司收款配置','Company collection settings')}}</a>
    </nav>
    <p class="nav-group">{{t('个人中心','My account')}}</p>
    <nav>
     <a href="/participation/" :class="{selected:mode==='participation'}"><ElIcon><User/></ElIcon>{{t('我的参会','My participation')}}</a>
     <a href="/user/profile/"><ElIcon><User/></ElIcon>{{t('个人资料','Profile')}}</a>
     <a href="/user/dashboard/?legacy=1"><ElIcon><Clock/></ElIcon>{{t('日程与参会记录','Schedule & participation')}}</a>
    </nav>
    <div class="sidebar-bottom"><span class="online-dot"></span>{{t('遇见科技 · 连接学术','Meet Technology · Connecting research')}}<a href="/">{{t('返回平台首页','Platform home')}} <ElIcon><ArrowRight/></ElIcon></a></div>
   </aside>
   <div class="workspace-content">
    <div class="workspace-breadcrumb"><a href="/">{{t('遇见科技','Meet Technology')}}</a><span>/</span><span>{{heading}}</span></div>
    <header class="workspace-heading"><div><h1>{{heading}}</h1><p>{{['payments','company-payments','payment-detail'].includes(mode)?t('统一公司收款，查看付款、退款与开票记录。','Company collection, payment verification, refunds and invoices.'):mode==='operations'?t('管理报名、稿件和评审，跟进会议筹备进度。','Manage registrations, submissions and reviewing.'):mode==='participation'?t('查看报名与稿件状态，处理分配给您的审稿任务。','View your registrations, submissions and assigned reviews.'):mode==='directory'?t('寻找下一场学术相遇，探索新的研究与交流机会。','Find your next academic gathering and explore new ideas.'):mode==='create'?t('填写会议信息，为您的学术交流建立专属网站。','Give your academic gathering a dedicated online home.'):mode==='website'?t('完善内容、预览效果，并决定何时与参会者分享。','Edit the content, preview your website and publish when ready.'):t('在这里筹备、管理和发布您的会议网站。','Organize, manage and publish your conference websites here.')}}</p></div><ElButton v-if="mode==='organizer'||mode==='directory'" tag="a" href="/conference/create/" type="primary" :icon="Plus">{{t('创建会议','Create conference')}}</ElButton><ElButton v-if="mode==='website'||mode==='operations'" tag="a" :href="mode==='operations'?`/conference/${eventId}/`:'/organizer/'" :icon="Back">{{mode==='operations'?t('返回网站工作台','Website workspace'):t('返回我的会议','My conferences')}}</ElButton></header>
    <ElAlert v-if="error" :title="error" type="error" show-icon :closable="false" class="workspace-error"/>
    <a v-if="mode==='organizer'||mode==='website'||mode==='operations'" class="mobile-participation" href="/user/dashboard/?legacy=1"><ElIcon><Clock/></ElIcon>{{t('日程与参会记录','Schedule & participation')}}<ElIcon><ArrowRight/></ElIcon></a>

    <template v-if="mode==='directory'">
     <section class="directory-intro"><div><span class="intro-line"></span><h2>{{t('让每一次相遇，都带来新的可能','Every gathering opens new possibilities')}}</h2><p>{{t('浏览已发布的会议，了解会议主题、时间与举办地点。','Explore published conferences, their topics, dates and venues.')}}</p></div><div class="directory-orbit" aria-hidden="true"><span></span><span></span><span></span><ElIcon><Collection/></ElIcon></div></section>
     <section class="surface directory-results"><form class="workspace-toolbar" @submit.prevent="search"><div class="search-field"><ElInput v-model="keyword" :prefix-icon="Search" :placeholder="t('搜索会议名称或地点','Search by title or location')" clearable aria-label="Search conferences" @clear="search"/><ElButton type="primary" native-type="submit">{{t('搜索','Search')}}</ElButton></div><span class="result-count">{{t('共','')}} {{total}} {{t('场公开会议','public conferences')}}</span></form>
      <ElSkeleton v-if="loading" :rows="5" animated/>
      <ElEmpty v-else-if="!events.length" :description="t('未找到会议，试试其他关键词。','No conferences found. Try another search.')"/>
      <div v-else class="directory-grid"><article v-for="(event,index) in events" :key="event.id" class="directory-card"><a :href="event.url" class="directory-cover" :class="`cover-tone-${index%3}`" tabindex="-1" aria-hidden="true"><span class="cover-lines"></span><span>{{new Date(event.start).getFullYear()}}</span><ElIcon><Collection/></ElIcon></a><div class="directory-card-content"><div class="card-topline"><ElTag size="small" :type="event.phase==='ended'?'info':event.phase==='ongoing'?'success':'primary'" effect="plain">{{phaseLabel(event)}}</ElTag><time>{{date(event.start)}}</time></div><h3><a :href="event.url">{{event.title}}</a></h3><p>{{event.description||t('点击查看会议详情。','View conference details.')}}</p><div class="card-location"><span><ElIcon><Location/></ElIcon>{{event.location||t('地点待定','Location to be announced')}}</span><a :href="event.url">{{t('查看会议','View website')}}<ElIcon><ArrowRight/></ElIcon></a></div></div></article></div>
      <ElPagination v-if="total>12" v-model:current-page="page" :page-size="12" :total="total" layout="prev, pager, next" @current-change="load"/>
     </section>
    </template>

    <template v-else-if="mode==='organizer'">
     <section class="welcome-panel"><div class="welcome-copy"><div class="welcome-avatar">{{initials}}</div><div><h2>{{t('欢迎回来','Welcome back')}}{{user?.name?'，'+user.name:''}}</h2><p>{{t('从一场会议开始，让思想在这里相遇。','Bring people and ideas together with your next conference.')}}</p></div></div><a href="/conference/create/">{{t('开始筹备新会议','Start a new conference')}}<ElIcon><ArrowRight/></ElIcon></a></section>
     <div class="workspace-stats"><div><span class="stat-icon blue"><ElIcon><Calendar/></ElIcon></span><span>{{t('全部会议','All conferences')}}<strong>{{events.length}}</strong></span></div><div><span class="stat-icon green"><ElIcon><Promotion/></ElIcon></span><span>{{t('已发布','Published')}}<strong>{{published}}</strong></span></div><div><span class="stat-icon amber"><ElIcon><Document/></ElIcon></span><span>{{t('私密草稿','Private drafts')}}<strong>{{events.length-published}}</strong></span></div><div><span class="stat-icon violet"><ElIcon><Clock/></ElIcon></span><span>{{t('进行中及待举办','Current & upcoming')}}<strong>{{upcoming}}</strong></span></div></div>
     <section class="surface my-conferences"><div class="surface-heading"><h2>{{t('会议网站','Conference websites')}}</h2><ElButton text :icon="Refresh" @click="load">{{t('刷新','Refresh')}}</ElButton></div><div class="workspace-toolbar"><ElInput v-model="keyword" :prefix-icon="Search" :placeholder="t('搜索我的会议','Search my conferences')" clearable/><ElSelect v-model="filter" :aria-label="t('发布状态','Publication status')"><ElOption value="all" :label="t('全部状态','All statuses')"/><ElOption value="published" :label="t('已发布','Published')"/><ElOption value="draft" :label="t('私密草稿','Private drafts')"/></ElSelect></div>
      <ElSkeleton v-if="loading" :rows="5" animated/>
      <template v-else>
       <ElTable :data="filtered" class="desktop-event-table" row-key="id" :empty-text="t('暂无会议，点击“创建会议”开始。','No conferences yet. Create your first conference.')"><ElTableColumn :label="t('会议名称','Conference')" min-width="260"><template #default="{row}"><div class="table-conference"><span class="table-icon"><ElIcon><Monitor/></ElIcon></span><div><a :href="row.builder_url">{{row.title}}</a><small><ElIcon><Location/></ElIcon>{{row.location}}</small></div></div></template></ElTableColumn><ElTableColumn :label="t('会议日期','Dates')" min-width="175"><template #default="{row}"><div class="table-date">{{date(row.start)}}<small>{{t('至','to')}} {{date(row.end)}}</small></div></template></ElTableColumn><ElTableColumn :label="t('状态','Status')" min-width="120"><template #default="{row}"><ElTag :type="row.published?'success':'warning'" effect="light">{{row.published?t('已发布','Published'):t('私密草稿','Private draft')}}</ElTag></template></ElTableColumn><ElTableColumn :label="t('操作','Actions')" width="176"><template #default="{row}"><ElButton tag="a" :href="row.builder_url" type="primary" link>{{t('管理网站','Manage')}}</ElButton><ElButton tag="a" :href="row.url" target="_blank" rel="noopener" link>{{t('预览','Preview')}}</ElButton></template></ElTableColumn></ElTable>
       <div class="mobile-event-list"><ElEmpty v-if="!filtered.length" :description="t('暂无会议','No conferences')"/><article v-for="event in filtered" :key="event.id"><div><ElTag :type="event.published?'success':'warning'" size="small">{{event.published?t('已发布','Published'):t('草稿','Draft')}}</ElTag><h3>{{event.title}}</h3><p>{{date(event.start)}} · {{event.location}}</p></div><ElButton tag="a" :href="event.builder_url" type="primary" plain>{{t('管理网站','Manage')}}</ElButton></article></div>
      </template>
      <div class="table-note"><ElIcon><InfoIcon/></ElIcon>{{t('草稿仅本会议管理者可见；发布后将展示在公开会议目录。','Drafts are visible only to conference managers. Published websites appear in the public directory.')}}</div>
     </section>
    </template>

    <template v-else-if="mode==='create'">
     <div class="create-layout"><section class="surface create-panel"><ElSteps :active="0" finish-status="success" simple><ElStep :title="t('填写信息','Details')"/><ElStep :title="t('完善网站','Edit website')"/><ElStep :title="t('发布分享','Publish')"/></ElSteps><div class="surface-heading"><div><h2>{{t('会议基本信息','Conference details')}}</h2><p>{{t('创建后可继续修改，网站将先保存为私密草稿。','You can edit these details later. Your website starts as a private draft.')}}</p></div></div>
      <ElForm id="builder-form" ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="create"><ElFormItem :label="t('会议名称','Conference title')" prop="title"><ElInput v-model="form.title" name="title" maxlength="200" show-word-limit :placeholder="t('例如：2027 年先进材料学术研讨会','e.g. Advanced Materials Symposium 2027')"/></ElFormItem><div class="form-two-cols"><ElFormItem :label="t('开始时间','Start time')" prop="start"><ElDatePicker v-model="form.start" name="start" type="datetime" value-format="YYYY-MM-DDTHH:mm" format="YYYY-MM-DD HH:mm" :placeholder="t('选择开始时间','Select start time')"/></ElFormItem><ElFormItem :label="t('结束时间','End time')" prop="end"><ElDatePicker v-model="form.end" name="end" type="datetime" value-format="YYYY-MM-DDTHH:mm" format="YYYY-MM-DD HH:mm" :placeholder="t('选择结束时间','Select end time')"/></ElFormItem></div><p class="field-note">{{t('会议时间使用中国标准时间（UTC+8）。','Times use China Standard Time (UTC+8).')}}</p><ConferenceMetadataFields :model="form" :language="language" :disabled="busy"/><ElFormItem :label="t('会议简介','Conference introduction')" prop="description"><ElInput v-model="form.description" name="description" type="textarea" :rows="5" maxlength="10000" show-word-limit :placeholder="t('介绍会议主题、交流方向及参会对象…','Introduce the topics, goals and audience…')"/></ElFormItem>
       <ElFormItem :label="t('网站模板','Website template')"><ElRadioGroup v-model="form.template" class="template-selector"><ElRadioButton value="academic-full"><span class="template-preview academic-full"><b></b><i></i><i></i></span><strong>{{t('完整学术会议','Complete academic conference')}}</strong><small>{{t('横幅、嘉宾、动态与单位侧栏','Banner, speakers, news & organization sidebar')}}</small></ElRadioButton><ElRadioButton value="academic"><span class="template-preview academic"><i></i><i></i><i></i></span><strong>{{t('学术蓝','Academic blue')}}</strong><small>{{t('学术会议与研究交流','Research & academic exchange')}}</small></ElRadioButton><ElRadioButton value="industry"><span class="template-preview industry"><i></i><i></i><i></i></span><strong>{{t('科技绿','Technology green')}}</strong><small>{{t('产业论坛与创新交流','Industry & innovation')}}</small></ElRadioButton></ElRadioGroup></ElFormItem>
       <div class="form-actions"><ElButton type="primary" native-type="submit" :loading="busy" :icon="Plus">{{t('一键生成会议网站','Generate conference website')}}</ElButton><ElButton tag="a" href="/organizer/">{{t('取消','Cancel')}}</ElButton></div>
      </ElForm>
     </section><aside class="create-guide"><div class="guide-illustration"><ElIcon><Monitor/></ElIcon><span><ElIcon><Check/></ElIcon></span></div><h2>{{t('会议网站，从这里开始','Your conference starts here')}}</h2><p>{{t('一个专属网站，集中呈现会议的每一项重要信息。','One dedicated website for all your important conference information.')}}</p><ul><li><ElIcon><Check/></ElIcon><div><strong>{{t('栏目自动生成','Ready-to-edit sections')}}</strong><span>{{t('委员会、主题、日程、地点、通知与联系信息。','Committee, topics, schedule, venue, notices and contacts.')}}</span></div></li><li><ElIcon><Check/></ElIcon><div><strong>{{t('内容由您掌控','You control the content')}}</strong><span>{{t('自由编辑会议内容，预览后再发布。','Edit your content and preview it before publishing.')}}</span></div></li><li><ElIcon><Check/></ElIcon><div><strong>{{t('发布时机由您决定','Publish when ready')}}</strong><span>{{t('草稿保持私密，发布后可随时撤回。','Drafts stay private. Published websites can be withdrawn.')}}</span></div></li></ul><a href="/category/1/">{{t('看看其他会议网站','Explore conference websites')}}<ElIcon><ArrowRight/></ElIcon></a></aside></div>
    </template>

    <template v-else-if="['payments','company-payments','payment-detail'].includes(mode)"><PaymentWorkspace :mode="mode" :event-id="eventId" :language="language"/></template>
    <template v-else-if="mode==='operations'||mode==='participation'"><BusinessWorkspace :mode="mode" :event-id="eventId" :language="language"/></template>
    <template v-else-if="mode==='website'">
     <ElSkeleton v-if="loading" :rows="8" animated/>
     <template v-else-if="website"><section class="surface website-summary"><div class="website-symbol"><ElIcon><Monitor/></ElIcon></div><div class="website-summary-copy"><div class="website-state"><ElTag id="builder-state" :type="website.published?'success':'warning'">{{website.published?t('已发布','Published'):t('私密草稿','Private draft')}}</ElTag><span>{{t('会议网站','Conference website')}} #{{website.id}}</span></div><h2>{{website.title}}</h2><p><ElIcon><Calendar/></ElIcon>{{date(website.start)}} — {{date(website.end)}}<span><ElIcon><Location/></ElIcon>{{website.location}}</span></p></div><ElButton tag="a" :href="website.url" target="_blank" rel="noopener" :icon="View" @click.prevent="siteEditor?.preview()">{{t('预览网站','Preview website')}}</ElButton></section>
      <ElTabs v-model="tab" class="website-tabs"><ElTabPane :label="t('发布概览','Publication overview')" name="overview"><div class="website-columns"><section class="surface publication-panel"><div class="surface-heading"><h2>{{t('发布与分享','Publish and share')}}</h2><ElIcon><Promotion/></ElIcon></div><div class="publication-status" :class="{published:website.published}"><span class="publication-icon"><ElIcon><Check v-if="website.published"/><Document v-else/></ElIcon></span><h3>{{website.published?t('您的会议网站已上线','Your conference website is live'):t('网站已生成，等待您的发布','Your website is ready to publish')}}</h3><p>{{website.published?t('参会者可以访问会议网站，会议已展示在公开目录中。','Participants can visit your website. It appears in the public conference directory.'):t('目前仅本会议管理者可以访问。完善内容并预览后，即可发布。','Only conference managers can access it. Edit and preview the content, then publish.')}}</p><ElButton id="builder-publish" :type="website.published?'default':'primary'" :loading="busy" :icon="Promotion" @click="publish">{{website.published?t('撤回发布','Withdraw website'):t('发布会议网站','Publish website')}}</ElButton></div><div id="builder-share" v-if="website.published" class="share-box"><label for="website-url">{{t('公开会议网址','Public website address')}}</label><div><ElInput id="website-url" :model-value="websiteUrl" readonly/><ElButton id="builder-copy" :icon="Link" @click="copy">{{t('复制网址','Copy link')}}</ElButton></div></div></section><section class="surface next-steps"><h2>{{t('完善您的会议网站','Complete your website')}}</h2><a :href="`/conference/${eventId}/operations/`"><span class="action-icon"><ElIcon><User/></ElIcon></span><div><strong>{{t('报名与投稿管理','Registration & submission management')}}</strong><p>{{t('配置报名、查看名单并管理稿件评审','Configure registration, manage attendees and review submissions')}}</p></div><ElIcon><ArrowRight/></ElIcon></a><a :href="`/event/${eventId}/manage/layout/menu/`"><span class="action-icon"><ElIcon><Document/></ElIcon></span><div><strong>{{t('编辑网站栏目','Edit website sections')}}</strong><p>{{t('完善委员会、日程、通知等内容','Add committee members, schedules and notices')}}</p></div><ElIcon><ArrowRight/></ElIcon></a><a :href="`/conference/${eventId}/?tab=settings#conference-basic`" @click.prevent="openBasic"><span class="action-icon"><ElIcon><Setting/></ElIcon></span><div><strong>{{t('会议基本设置','Conference settings')}}</strong><p>{{t('修改会议名称、时间与简介','Update the title, dates and introduction')}}</p></div><ElIcon><ArrowRight/></ElIcon></a><a :href="`/conference/${eventId}/?tab=design#appearance-presets`" @click.prevent="openAppearance"><span class="action-icon"><ElIcon><Monitor/></ElIcon></span><div><strong>{{t('调整网站外观','Customize appearance')}}</strong><p>{{t('选择预制外观，调整网站布局与配色','Choose a preset appearance, layout and color')}}</p></div><ElIcon><ArrowRight/></ElIcon></a></section></div></ElTabPane>
       <ElTabPane :label="t('首页设计','Homepage design')" name="design"><SiteContentEditor ref="siteEditor" :event-id="eventId" :website-url="websiteUrl" :language="language"/></ElTabPane>
       <ElTabPane :label="t('设为栏目的内容','Website section content')" name="content"><section class="surface content-panel"><div class="surface-heading"><div><h2>{{t('让参会者快速找到所需信息','Help participants find what they need')}}</h2><p>{{t('使用栏目编辑器修改内容、调整顺序或添加新的页面。','Use the section editor to edit content, reorder sections or add pages.')}}</p></div><ElButton tag="a" :href="`/event/${eventId}/manage/layout/menu/`" type="primary" :icon="Document">{{t('打开栏目编辑器','Open section editor')}}</ElButton></div><div class="section-guide-grid"><article v-for="item in [[t('会议日程','Conference schedule'),t('发布会议安排与报告时间。','Publish the program and presentation times.')],[t('注册缴费','Registration & fees'),t('说明参会方式、报名费用与缴费安排。','Explain registration options, fees and payment arrangements.')],[t('场地与交通','Venue & transport'),t('提供会场地址、交通路线与到达指南。','Provide venue addresses, transport routes and arrival guidance.')],[t('酒店介绍','Hotel information'),t('介绍推荐酒店、房型与预订方式。','Introduce recommended hotels, room types and booking options.')],[t('联系我们','Contact us'),t('填写主办方和对外联系方式。','Add organizer details and public contacts.')],[t('其他','Other'),t('按需添加会议通知及其他独立页面。','Add conference notices and other pages as needed.')]]" :key="item[0]"><ElIcon><Document/></ElIcon><h3>{{item[0]}}</h3><p>{{item[1]}}</p></article></div><div class="content-business-links"><ElButton tag="a" :href="`/event/${eventId}/registrations/`">{{t('参会注册快速通道','Registration quick link')}}</ElButton><ElButton tag="a" :href="`/event/${eventId}/abstracts/`">{{t('会议投稿快速通道','Submission quick link')}}</ElButton><ElButton tag="a" :href="`/conference/${eventId}/operations/`">{{t('报名、投稿与登记管理','Registration & submission management')}}</ElButton></div><p class="field-note">{{t('以上为栏目内容建议。已保存页面与快速通道继续保留，实际内容以栏目编辑器为准。','These are suggested section contents. Existing pages and quick links are preserved; the section editor shows your saved content.')}}</p></section></ElTabPane>
       <ElTabPane :label="t('站点设置','Website settings')" name="settings"><section class="surface settings-panel"><h2>{{t('会议与网站设置','Conference and website settings')}}</h2><BasicConferenceEditor :event-id="eventId" :language="language" @saved="basicSaved"/><div class="settings-row"><div><h3>{{t('网站外观','Website appearance')}}</h3><p>{{t('会议标志、横幅和主题配色。','Conference logo, banner and theme colors.')}}</p></div><ElButton tag="a" :href="`/conference/${eventId}/?tab=design#appearance-presets`" @click.prevent="openAppearance">{{t('调整外观','Customize')}}</ElButton></div><div class="settings-row"><div><h3>{{t('管理权限','Management access')}}</h3><p>{{t('邀请协作管理者，设置会议访问权限。','Invite fellow organizers and configure conference access.')}}</p></div><ElButton tag="a" :href="`/event/${eventId}/manage/protection/`">{{t('管理权限','Manage access')}}</ElButton></div></section></ElTabPane></ElTabs>
     </template>
    </template>
    <p class="workspace-footnote">{{t('遇见科技会议服务平台','Meet Technology Conference Service Platform')}}</p>
   </div>
  </div>
 </ElConfigProvider>
</template>

<style scoped>
.content-business-links{display:flex;gap:12px;flex-wrap:wrap;margin:22px 0}.content-business-links :deep(.el-button){margin-left:0}
.template-selector{grid-template-columns:repeat(3,minmax(0,1fr))}.template-preview.academic-full{padding-top:36px;background:#f4f6f8;gap:5px}.template-preview.academic-full:before{height:25px;background:linear-gradient(120deg,#18415f,#36718b)}.template-preview.academic-full:after{content:'';position:absolute;top:25px;left:0;right:0;height:6px;background:#fa7d4b}.template-preview.academic-full b{position:absolute;top:9px;left:10px;width:40%;height:4px;background:#ffffffc9}.template-preview.academic-full i:first-of-type{flex:3;border-top:3px solid #fa7d4b}.template-preview.academic-full i:last-child{flex:1;border-top:3px solid #fa7d4b}
@media(max-width:600px){.template-selector{grid-template-columns:1fr}.template-selector :deep(.el-radio-button__inner){display:grid;grid-template-columns:90px 1fr;column-gap:12px;align-items:center}.template-selector .template-preview{grid-row:1/3;height:64px}.template-selector strong{margin:3px 0;align-self:end}.template-selector small{align-self:start}.template-preview.academic-full{padding-top:36px}}
</style>

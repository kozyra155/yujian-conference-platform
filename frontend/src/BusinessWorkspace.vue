<script setup>
import {computed,onUnmounted,ref,watch} from 'vue';
import {ElAlert,ElButton,ElEmpty,ElIcon,ElInput,ElOption,ElSelect,ElSkeleton,ElTabs,ElTabPane,ElTag} from 'element-plus';
import {ArrowRight,Calendar,Document,Location,Refresh,Search,Setting,User} from '@element-plus/icons-vue';

const props=defineProps({mode:{type:String,required:true},eventId:Number,language:{type:String,default:'zh'}});
const t=(zh,en)=>props.language==='en'?en:zh;
const data=ref(null),loading=ref(true),error=ref(0),tab=ref('registration'),keyword=ref(''),state=ref('all');
let controller;
const operations=computed(()=>props.mode==='operations');
const registration=computed(()=>data.value?.registration||{});
const submission=computed(()=>data.value?.submission||{});
const enabled=key=>data.value?.features?.[key]!==false&&(key==='registration'?registration.value.enabled:submission.value.enabled)!==false;
const records=computed(()=>operations.value?tab.value==='registration'?registration.value.forms||[]:submission.value.recent||[]:tab.value==='registration'?data.value?.registrations||[]:tab.value==='submission'?data.value?.submissions||[]:data.value?.reviews||[]);
const statusLabels={
 complete:['报名成功','Registered'],pending:['待审核','Pending approval'],rejected:['已拒绝','Rejected'],withdrawn:['已撤回','Withdrawn'],unpaid:['待付款','Awaiting payment'],
 submitted:['已提交','Submitted'],accepted:['已录用','Accepted'],merged:['已合并','Merged'],duplicate:['重复稿件','Duplicate'],invited:['已邀请','Invited'],
 open:['开放中','Open'],closed:['已关闭','Closed'],scheduled:['尚未开放','Scheduled'],not_started:['尚未开放','Not open yet'],active:['开放中','Open'],
 disabled:['未启用','Disabled'],finished:['已结束','Finished'],started:['开放中','Open'],not_open:['尚未开放','Not open yet']
};
const statusLabel=value=>statusLabels[value]?t(...statusLabels[value]):value?String(value).replaceAll('_',' '):t('未提供状态','Status unavailable');
const statusType=value=>['complete','accepted','open','active','started'].includes(value)?'success':['pending','submitted','invited','scheduled','unpaid'].includes(value)?'warning':['rejected'].includes(value)?'danger':'info';
const states=computed(()=>[...new Set(records.value.map(item=>item.state).filter(Boolean))]);
const filtered=computed(()=>records.value.filter(item=>(state.value==='all'||item.state===state.value)&&`${item.title||''} ${item.event_title||''} ${item.form_title||''} ${item.submitter||''} ${item.number||''} ${(item.tracks||[]).map(track=>track.title).join(' ')}`.toLocaleLowerCase().includes(keyword.value.trim().toLocaleLowerCase())));
const errorMessage=computed(()=>error.value===401?t('登录状态已失效，请重新登录后查看。','Your session expired. Log in to view your records.'):error.value===403?t('您没有查看权限，或会议已撤回。','You do not have access, or the conference has been withdrawn.'):error.value===404?t('未找到您可以访问的会议。','No accessible conference was found.'):t('暂时无法载入记录，请重试。','Records could not be loaded. Try again.'));
const date=value=>{if(!value||Number.isNaN(new Date(value).getTime()))return '';return new Intl.DateTimeFormat(props.language==='en'?'en-GB':'zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'short',day:'numeric'}).format(new Date(value));};
const eventDates=item=>[date(item.start),date(item.end)].filter(Boolean).filter((value,index,array)=>index===0||value!==array[0]).join(' — ');
const eventLink=item=>item.event_url||(item.event_id?`/event/${item.event_id}/`:null);
const emptyText=computed(()=>keyword.value.trim()||state.value!=='all'?t('没有匹配的记录','No matching records'):operations.value?tab.value==='registration'?t('尚未创建报名表','No registration forms yet'):t('暂无稿件','No submissions yet'):tab.value==='registration'?t('暂无报名记录','No registrations yet'):tab.value==='submission'?t('暂无投稿记录','No submissions yet'):t('暂无审稿任务','No review tasks yet'));
async function load(){
 controller?.abort();controller=new AbortController();const requestController=controller;
 loading.value=true;error.value=0;data.value=null;
 try{
  const response=await fetch(operations.value?`/api/conferences/${props.eventId}/operations`:'/api/participation/',{credentials:'same-origin',cache:'no-store',signal:requestController.signal});
  if(!response.ok){error.value=response.status;return;}
  const result=await response.json();if(controller===requestController)data.value=result;
 }catch(e){if(e.name!=='AbortError'&&controller===requestController)error.value=500;}finally{if(controller===requestController)loading.value=false;}
}
watch(()=>[props.mode,props.eventId],()=>{tab.value='registration';keyword.value='';state.value='all';load();},{immediate:true});
watch(tab,()=>{keyword.value='';state.value='all';});
onUnmounted(()=>controller?.abort());
</script>

<template>
 <section class="business-workspace" data-test="business-workspace" :aria-busy="loading">
  <div class="business-topbar">
   <div v-if="operations&&data?.event" class="business-event"><span class="business-symbol"><ElIcon><Calendar/></ElIcon></span><div><h2>{{data.event.title}}</h2><a v-if="data.event.url" :href="data.event.url">{{t('查看会议网站','Conference website')}} <ElIcon><ArrowRight/></ElIcon></a></div></div>
   <p v-else class="business-intro">{{t('报名、稿件与审稿安排，集中在这里查看。','Your registrations, submissions and review assignments in one place.')}}</p>
   <div class="business-actions"><ElButton v-if="operations&&data?.event" tag="a" :href="`/conference/${data.event.id}/payments/`">{{t('收费与订单','Fees & orders')}}</ElButton><ElButton v-if="operations&&data?.event?.builder_url" tag="a" :href="data.event.builder_url">{{t('网站工作台','Website workspace')}}</ElButton><ElButton :icon="Refresh" :loading="loading" @click="load">{{t('刷新','Refresh')}}</ElButton></div>
  </div>
  <ElAlert v-if="error" data-test="business-error" :title="errorMessage" type="error" show-icon :closable="false"><template #default><div class="business-error-actions"><ElButton v-if="error===401" tag="a" :href="`/login/?next=${encodeURIComponent(operations?`/conference/${eventId}/operations/`:'/participation/')}`">{{t('登录','Log in')}}</ElButton><ElButton @click="load">{{t('重试','Retry')}}</ElButton></div></template></ElAlert>
  <ElSkeleton v-if="loading" :rows="8" animated/>
  <div v-else-if="data" data-test="business-ready">
   <ElAlert v-if="operations&&data.event.locked" class="business-lock" type="info" show-icon :closable="false" :title="t('会议已锁定。您仍可查看记录，修改操作受会议锁定限制。','This conference is locked. Records remain available; changes are restricted.')"/>
   <div class="business-stats" v-if="operations">
    <article><ElIcon><User/></ElIcon><div><strong>{{registration.total||0}}</strong><span>{{t('报名人数','Registrations')}}</span></div></article>
    <article><ElIcon><User/></ElIcon><div><strong>{{registration.pending||0}}</strong><span>{{t('待审核报名','Awaiting approval')}}</span></div></article>
    <article><ElIcon><Document/></ElIcon><div><strong>{{submission.total||0}}</strong><span>{{t('收到稿件','Submissions')}}</span></div></article>
    <article><ElIcon><Document/></ElIcon><div><strong>{{submission.pending||0}}</strong><span>{{t('待处理稿件','Awaiting decision')}}</span></div></article>
   </div>
   <div class="business-stats participation-stats" v-else>
    <article><ElIcon><User/></ElIcon><div><strong>{{data.registrations.length}}</strong><span>{{t('我的报名','My registrations')}}</span></div></article>
    <article><ElIcon><Document/></ElIcon><div><strong>{{data.submissions.length}}</strong><span>{{t('我的稿件','My submissions')}}</span></div></article>
    <article><ElIcon><Document/></ElIcon><div><strong>{{data.reviews.reduce((count,item)=>count+item.tracks.reduce((sum,track)=>sum+track.count,0),0)}}</strong><span>{{t('可审稿件','Reviewable abstracts')}}</span></div></article>
   </div>
   <ElTabs v-model="tab" class="business-tabs">
    <ElTabPane name="registration" :label="operations?t('报名管理','Registration management'):`${t('我的报名','My registrations')} (${data.registrations.length})`"/>
    <ElTabPane name="submission" :label="operations?t('投稿与审稿','Submissions & reviewing'):`${t('我的稿件','My submissions')} (${data.submissions.length})`"/>
    <ElTabPane v-if="!operations" name="review" :label="`${t('审稿任务','Review tasks')} (${data.reviews.length})`"/>
   </ElTabs>
   <section v-if="operations&&!enabled(tab==='registration'?'registration':'abstracts')" class="surface business-disabled">
    <ElIcon><Setting/></ElIcon><h3>{{tab==='registration'?t('尚未启用报名功能','Registration is disabled'):t('尚未启用投稿功能','Abstract submission is disabled')}}</h3><p>{{t('先在会议功能配置中启用，即可开始设置和接收记录。','Enable this feature in conference settings to set it up and receive records.')}}</p><ElButton v-if="data.event.feature_url" tag="a" :href="data.event.feature_url" type="primary">{{t('打开功能配置','Open feature settings')}}</ElButton>
   </section>
   <section v-else class="surface business-panel">
    <div class="business-panel-heading" v-if="operations">
     <div><h3>{{tab==='registration'?t('会议报名表','Registration forms'):t('最近稿件','Recent submissions')}}</h3><p v-if="tab==='submission'">{{t('展示最近 20 篇稿件；完整名单与审稿操作请进入稿件管理。','Showing the 20 most recent submissions. Open abstract management for the full list and reviewing.')}}</p></div>
     <div class="business-actions" v-if="tab==='registration'"><ElButton v-if="registration.links?.manage_url" tag="a" :href="registration.links.manage_url">{{t('管理报名','Manage registration')}}</ElButton><ElButton v-if="registration.links?.create_url" tag="a" :href="registration.links.create_url" type="primary">{{t('创建报名表','Create form')}}</ElButton></div>
     <div class="business-actions" v-else><ElButton v-if="submission.links?.settings_url" tag="a" :href="submission.links.settings_url">{{t('征稿设置','Call for abstracts settings')}}</ElButton><ElButton v-if="submission.links?.reviewing_url" tag="a" :href="submission.links.reviewing_url">{{t('审稿管理','Review management')}}</ElButton><ElButton v-if="submission.links?.list_url" tag="a" :href="submission.links.list_url" type="primary">{{t('全部稿件','All submissions')}}</ElButton></div>
    </div>
    <div class="business-call-state" v-if="operations&&tab==='submission'"><span>{{t('征稿状态','Call for abstracts')}}</span><ElTag :type="statusType(submission.state)">{{statusLabel(submission.state)}}</ElTag><span v-for="(count,key) in submission.counts" :key="key" class="business-state-count">{{statusLabel(key)}} <b>{{count}}</b></span></div>
    <div class="business-filters">
     <ElInput data-test="business-search" v-model="keyword" clearable :prefix-icon="Search" :placeholder="operations?t('搜索名称、稿件或提交人','Search titles or submitters'):t('搜索会议、稿件或专题','Search conferences, abstracts or tracks')" :aria-label="t('搜索业务记录','Search records')"/>
     <ElSelect v-if="tab!=='review'" v-model="state" :aria-label="t('按状态筛选','Filter by status')"><ElOption value="all" :label="t('全部状态','All statuses')"/><ElOption v-for="value in states" :key="value" :value="value" :label="statusLabel(value)"/></ElSelect>
     <span class="business-result-count">{{filtered.length}} {{t('条记录','records')}}</span>
    </div>
    <ElEmpty v-if="!filtered.length" :description="emptyText" :image-size="88"><ElButton v-if="!operations" tag="a" href="/category/1/" type="primary">{{t('浏览会议','Browse conferences')}}</ElButton></ElEmpty>
    <div v-else class="business-records">
     <article v-for="item in filtered" :key="item.id||item.event_id" class="business-record" :data-test="operations&&tab==='registration'?'registration-form':operations?'recent-submission':'participation-record'">
      <div class="business-record-main">
       <div class="business-record-heading"><span v-if="item.number" class="business-number">#{{item.number}}</span><h3>{{operations?item.title:tab==='submission'?item.title:item.event_title}}</h3><ElTag v-if="item.state" :type="statusType(item.state)">{{statusLabel(item.state)}}</ElTag></div>
       <template v-if="operations&&tab==='registration'"><p class="business-record-meta"><span>{{t('报名人数','Registrations')}} <b>{{item.count}}</b></span><span>{{t('待审核','Pending approval')}} <b>{{item.pending_count}}</b></span></p></template>
       <template v-else-if="operations"><p class="business-record-meta"><span v-if="item.submitter">{{item.submitter}}</span><span v-if="item.submitted">{{date(item.submitted)}}</span></p></template>
       <template v-else>
        <a v-if="tab==='submission'&&eventLink(item)" :href="eventLink(item)" class="business-conference-link">{{item.event_title}}</a><p v-else-if="tab==='submission'" class="business-record-meta">{{item.event_title}}</p>
        <p v-if="item.form_title" class="business-form-title">{{item.form_title}}</p>
        <p v-if="eventDates(item)||item.location" class="business-record-meta"><span v-if="eventDates(item)"><ElIcon><Calendar/></ElIcon>{{eventDates(item)}}</span><span v-if="item.location"><ElIcon><Location/></ElIcon>{{item.location}}</span></p>
        <div v-if="tab==='review'" class="business-review-tracks"><a v-for="track in item.tracks" :key="track.id" :href="track.url">{{track.title}}<span>{{track.count}} {{t('篇可审稿件','to review')}}</span><ElIcon><ArrowRight/></ElIcon></a></div>
       </template>
      </div>
      <div class="business-record-actions">
       <template v-if="operations&&tab==='registration'"><ElButton v-if="item.url" tag="a" :href="item.url">{{t('配置与字段','Settings & fields')}}</ElButton><ElButton v-if="item.list_url" tag="a" :href="item.list_url" type="primary" plain>{{t('名单与导出','Participants & export')}}</ElButton><a v-if="item.list_url&&item.pending_count" :href="item.list_url">{{t('审核报名','Approve registrations')}}</a></template>
       <ElButton v-else-if="operations&&item.url" tag="a" :href="item.url" type="primary" plain>{{t('查看稿件','View abstract')}}</ElButton>
       <template v-else><ElButton v-if="tab==='registration'&&item.payment_url" tag="a" :href="item.payment_url" type="primary">{{item.state==='unpaid'?t('去付款','Pay now'):t('付款与发票','Payment & invoice')}}</ElButton><ElButton v-if="item.url" tag="a" :href="item.url" type="primary" plain>{{tab==='registration'?t('报名详情','Registration details'):tab==='submission'?t('稿件详情','Abstract details'):t('进入审稿','Open reviewing')}}</ElButton><a v-if="tab==='registration'&&item.can_modify&&item.url" :href="item.url">{{t('修改报名','Modify registration')}}</a><a v-if="tab==='submission'&&item.can_edit&&item.url" :href="item.url">{{t('编辑稿件','Edit abstract')}}</a><a v-if="tab==='registration'&&item.ticket_url" :href="item.ticket_url">{{t('参会凭证','Registration ticket')}}</a><a v-if="eventLink(item)" :href="eventLink(item)">{{t('会议网站','Conference website')}}</a></template>
      </div>
     </article>
    </div>
   </section>
  </div>
 </section>
</template>

<style scoped>
.business-workspace{min-width:0;color:#233b51}.business-topbar{display:flex;align-items:center;justify-content:space-between;gap:20px;margin:0 0 22px}.business-intro{font-size:13px;color:#738698;line-height:1.8;margin:0}.business-event{display:flex;align-items:center;gap:14px;min-width:0}.business-event>div{min-width:0}.business-event h2{font-size:20px;margin:0 0 7px;font-weight:600;overflow-wrap:anywhere}.business-event a{font-size:12px;display:inline-flex;align-items:center;gap:5px}.business-symbol{width:44px;height:48px;display:grid;place-items:center;background:#e4eff7;color:#246b9b;border-radius:8px;font-size:23px;flex-shrink:0}.business-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.business-actions :deep(.el-button)+.el-button,.business-record-actions :deep(.el-button)+.el-button{margin-left:0}.business-workspace a:not(.el-button){color:#246b9b;text-decoration:none}.business-workspace a:not(.el-button):hover{text-decoration:underline}.business-workspace a:focus-visible{outline:2px solid #246b9b;outline-offset:4px}.business-lock{margin-bottom:20px}.business-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin-bottom:22px}.business-stats article{padding:22px;display:flex;align-items:center;gap:18px;background:#fff;border:1px solid #e2e9f0;border-radius:8px}.business-stats article>.el-icon{width:44px;height:44px;color:#5088ae;background:#edf5fa;padding:11px;font-size:22px;border-radius:8px;flex-shrink:0}.business-stats strong{display:block;font-size:27px;font-weight:600;line-height:1.2;font-variant-numeric:tabular-nums}.business-stats span{display:block;margin-top:7px;font-size:11px;color:#738698;line-height:1.5}.participation-stats{grid-template-columns:repeat(3,minmax(0,1fr))}.business-tabs{margin-top:6px}.business-tabs :deep(.el-tabs__header){margin-bottom:20px}.business-panel{overflow:hidden}.business-panel-heading{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:24px;border-bottom:1px solid #edf1f5}.business-panel-heading>div:first-child{min-width:0}.business-panel h3{margin:0;font-size:15px;line-height:1.6;font-weight:600;overflow-wrap:anywhere}.business-panel-heading p{font-size:12px;color:#7b8c9b;line-height:1.8;margin:6px 0 0;max-width:65ch}.business-filters{display:flex;align-items:center;gap:12px;padding:20px 24px;border-bottom:1px solid #edf1f5}.business-filters>.el-input{max-width:400px;min-width:100px}.business-filters>.el-select{width:175px;flex-shrink:0}.business-result-count{font-size:12px;color:#7b8c9b;white-space:nowrap;margin-left:auto}.business-call-state{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:16px 24px 0;font-size:12px;color:#738698}.business-state-count{border-left:1px solid #dce4ec;padding-left:12px}.business-state-count b{font-weight:500;color:#233b51;margin-left:5px}.business-records{padding:0 24px}.business-record{display:flex;justify-content:space-between;align-items:center;gap:24px;padding:24px 0;border-bottom:1px solid #edf1f5}.business-record:last-child{border-bottom:0}.business-record-main{min-width:0;flex:1}.business-record-heading{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.business-record-heading h3{font-size:14px}.business-number{color:#8b9aaa;font-size:12px}.business-record-heading .el-tag{flex-shrink:0}.business-record-meta{display:flex;align-items:center;flex-wrap:wrap;gap:8px 22px;font-size:12px;color:#7b8c9b;line-height:1.8;margin:10px 0 0}.business-record-meta>span{display:inline-flex;align-items:center;gap:6px}.business-record-meta b{font-weight:500;color:#344e63}.business-record-actions{display:flex;gap:10px;align-items:center;justify-content:flex-end;flex-wrap:wrap;max-width:330px;flex-shrink:0}.business-record-actions>a:not(.el-button){font-size:12px;line-height:1.8}.business-conference-link{display:inline-block;font-size:12px;margin-top:9px}.business-form-title{font-size:12px;color:#506477;margin:8px 0 0}.business-review-tracks{display:grid;gap:9px;margin-top:14px}.business-review-tracks a{display:flex;align-items:center;gap:12px;font-size:13px;line-height:1.7;overflow-wrap:anywhere}.business-review-tracks span{color:#7b8c9b;font-size:11px}.business-review-tracks .el-icon{flex-shrink:0}.business-disabled{text-align:center;padding:44px 24px}.business-disabled>.el-icon{font-size:32px;color:#7899b2;margin-bottom:12px}.business-disabled h3{font-size:17px;margin:0 0 10px}.business-disabled p{font-size:13px;color:#738698;line-height:1.8;margin:0 auto 20px;max-width:60ch}.business-error-actions{margin:10px 0 2px;display:flex;gap:8px}.business-workspace :deep(.el-alert__content){min-width:0}.business-workspace :deep(.el-empty__description p){font-size:13px}.business-workspace :deep(.el-empty){padding:45px 15px}.business-workspace :deep(.el-tag){white-space:normal;height:auto;min-height:24px;padding:3px 7px;line-height:1.5}
@media(max-width:1100px){.business-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.participation-stats{grid-template-columns:repeat(3,minmax(0,1fr))}.business-panel-heading{align-items:flex-start;flex-direction:column}.business-record{gap:16px}.business-record-actions{max-width:220px}.business-stats article{gap:12px;padding:18px}}
@media(max-width:760px){.business-topbar{align-items:flex-start;flex-direction:column;gap:14px}.business-topbar>.business-actions{align-self:flex-start}.business-event h2{font-size:17px}.business-stats{gap:10px;margin-bottom:14px}.business-stats article{padding:16px 12px;gap:10px}.business-stats article>.el-icon{width:34px;height:34px;font-size:18px;padding:8px}.business-stats strong{font-size:24px}.business-stats span{font-size:10px}.participation-stats{grid-template-columns:repeat(3,minmax(0,1fr))}.participation-stats article{padding:16px 10px}.participation-stats article>.el-icon{display:none}.business-panel-heading{padding:18px}.business-panel-heading .business-actions{width:100%}.business-workspace .el-button{padding:8px 11px;font-size:12px;min-height:37px}.business-filters{padding:16px 18px;gap:10px;flex-wrap:wrap}.business-filters>.el-input{max-width:none;flex-basis:100%}.business-filters>.el-select{width:170px}.business-result-count{font-size:11px}.business-records{padding:0 18px}.business-record{align-items:flex-start;flex-direction:column;gap:15px;padding:21px 0}.business-record-main{width:100%}.business-record-actions{max-width:none;justify-content:flex-start;gap:10px 14px}.business-record-meta{font-size:11px;gap:7px 14px}.business-record-heading{gap:8px}.business-record-heading h3{font-size:13px}.business-panel-heading p{font-size:11px}.business-call-state{padding:15px 18px 0;gap:8px;font-size:11px}.business-state-count{padding-left:8px}.business-review-tracks a{flex-wrap:wrap;gap:5px 10px}.business-disabled{padding:32px 18px}.business-disabled p{font-size:12px}.business-tabs :deep(.el-tabs__item){font-size:12px;padding:0 12px}.business-tabs :deep(.el-tabs__item:nth-child(2)){padding-left:0}.business-tabs :deep(.el-tabs__item:last-child){padding-right:0}}
@media(max-width:380px){.business-stats article{gap:8px;padding:15px 10px}.business-stats article>.el-icon{width:29px;height:29px;padding:6px;font-size:17px}.business-stats strong{font-size:22px}.business-stats span{font-size:10px}.business-filters>.el-select{width:154px}.business-filters,.business-records,.business-panel-heading{padding-left:15px;padding-right:15px}.business-event h2{font-size:15px}.business-symbol{width:36px;height:42px}.business-intro{font-size:12px}}
</style>

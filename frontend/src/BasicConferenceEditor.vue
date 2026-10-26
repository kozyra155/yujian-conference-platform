<script setup>
import {computed,onMounted,onUnmounted,ref} from 'vue';
import {ElAlert,ElButton,ElDatePicker,ElForm,ElFormItem,ElInput,ElMessage,ElMessageBox,ElSkeleton,ElTag} from 'element-plus';
import ConferenceMetadataFields from './ConferenceMetadataFields.vue';
import {errorMessage} from './apiErrors.js';

const props=defineProps({eventId:{type:Number,required:true},language:{type:String,default:'zh'}});
const emit=defineEmits(['saved']);
const t=(zh,en)=>props.language==='en'?en:zh;
const form=ref(null),formRef=ref(),revision=ref(0),fingerprint=ref(''),loading=ref(true),saving=ref(false),error=ref(''),saved=ref('');
const dirty=computed(()=>form.value!==null&&JSON.stringify(form.value)!==saved.value);
const rules=computed(()=>Object.fromEntries([['title',t('请填写会议名称','Enter the conference title')],['start',t('请选择开始时间','Choose the start time')],['end',t('请选择结束时间','Choose the end time')],['description',t('请填写会议简介','Enter the conference introduction')]].map(([key,message])=>[key,[{required:true,whitespace:true,message,trigger:'change'}]])));
const phase=computed(()=>{if(!form.value?.start||!form.value?.end)return '';const now=Date.now();return now<new Date(form.value.start+'+08:00').getTime()?t('即将举办','Upcoming'):now<new Date(form.value.end+'+08:00').getTime()?t('进行中','Ongoing'):t('已结束','Ended');});
async function request(options={}){
 const headers={};
 if(options.method){const session=await window.MeetPortal.refreshSession();if(!session?.user)throw new Error(t('请重新登录后继续，当前填写内容已保留。','Log in again to continue. Your draft is retained.'));headers['Content-Type']='application/json';headers['X-CSRF-Token']=session.csrf_token;}
 const response=await fetch(`/api/conferences/${props.eventId}/basic`,{credentials:'same-origin',cache:'no-store',...options,headers});
 if(!response.ok){
  let data;try{data=await response.json();}catch{}
  throw new Error(response.status===409?t('其他管理者已更新会议信息，当前填写内容已保留。请先复制需要保留的内容，再重新载入。','Another organizer updated this conference. Your draft is retained. Copy any changes you need before reloading.'):response.status===403?t('您没有编辑权限，或会议已锁定。当前填写内容已保留。','Permission denied, or this conference is locked. Your draft is retained.'):response.status===401?t('请重新登录后继续，当前填写内容已保留。','Log in again to continue. Your draft is retained.'):errorMessage(data,t('保存失败，请检查会议基本信息后重试。','Could not save. Check the conference details and try again.')));
 }
 return response.json();
}
function apply(data){form.value=data.basic;revision.value=data.revision;fingerprint.value=data.fingerprint;saved.value=JSON.stringify(data.basic);}
async function load(){loading.value=true;error.value='';try{apply(await request());}catch(e){error.value=e.message;}finally{loading.value=false;}}
async function reload(){if(dirty.value){try{await ElMessageBox.confirm(t('重新载入会替换当前尚未保存的基本信息。','Reloading replaces your unsaved conference details.'),t('重新载入','Reload'),{confirmButtonText:t('重新载入','Reload'),cancelButtonText:t('取消','Cancel'),type:'warning'});}catch{return;}}await load();}
async function save(){
 if(saving.value||!await formRef.value.validate().catch(()=>false))return;
 if(new Date(form.value.end+'+08:00')<=new Date(form.value.start+'+08:00')){ElMessage.error(t('结束时间必须晚于开始时间。','End time must be after start time.'));return;}
 saving.value=true;error.value='';
 try{const data=await request({method:'PUT',body:JSON.stringify({revision:revision.value,fingerprint:fingerprint.value,basic:form.value})});apply(data);emit('saved',data.event);ElMessage.success(t('会议基本信息已保存','Conference details saved'));}
 catch(e){error.value=e.message;}finally{saving.value=false;}
}
function beforeUnload(event){if(dirty.value){event.preventDefault();event.returnValue='';}}
onMounted(()=>{load();window.addEventListener('beforeunload',beforeUnload);});
onUnmounted(()=>window.removeEventListener('beforeunload',beforeUnload));
</script>

<template>
 <div id="conference-basic" class="basic-conference-editor">
  <div class="basic-heading"><div><span class="basic-eyebrow">{{t('会议信息','CONFERENCE DETAILS')}}</span><h3>{{t('会议基本信息与简介','Conference details & introduction')}}</h3><p>{{t('编辑会议名称、时间、主办方和举办地点，供参会者了解会议安排。','Update the title, dates, organizer and location for your participants.')}}</p></div><ElTag v-if="dirty" type="warning">{{t('尚未保存','Unsaved changes')}}</ElTag></div>
  <ElAlert v-if="error" :title="error" type="error" show-icon :closable="false"/>
  <ElSkeleton v-if="loading" :rows="6" animated/>
  <ElForm v-else-if="form" ref="formRef" :model="form" :rules="rules" label-position="top" :disabled="saving" @submit.prevent="save">
   <ElFormItem :label="t('会议名称','Conference title')" prop="title"><ElInput v-model="form.title" name="title" maxlength="200" show-word-limit/></ElFormItem>
   <div class="basic-date-grid"><ElFormItem :label="t('开始时间','Start time')" prop="start"><ElDatePicker v-model="form.start" name="start" type="datetime" value-format="YYYY-MM-DDTHH:mm" format="YYYY-MM-DD HH:mm"/></ElFormItem><ElFormItem :label="t('结束时间','End time')" prop="end"><ElDatePicker v-model="form.end" name="end" type="datetime" value-format="YYYY-MM-DDTHH:mm" format="YYYY-MM-DD HH:mm"/></ElFormItem></div>
   <p class="basic-field-note">{{t('会议时间使用中国标准时间（UTC+8）。会议状态按起止时间自动更新：','Times use China Standard Time (UTC+8). Conference status follows these dates:')}} <strong>{{phase}}</strong></p>
   <ConferenceMetadataFields :model="form" :language="language" :disabled="saving"/>
   <ElFormItem :label="t('会议简介正文','Conference introduction text')" prop="description"><ElInput v-model="form.description" name="description" type="textarea" :rows="7" maxlength="20000" show-word-limit :placeholder="t('介绍会议主题、交流方向及参会对象','Introduce the conference topics, goals and audience')"/></ElFormItem>
   <p class="basic-field-note">{{t('简介配图可在“首页设计 → 会议简介”中添加。','Add introduction images in Homepage design → Introduction.')}}</p>
   <div class="basic-actions"><ElButton type="primary" native-type="submit" :loading="saving">{{t('保存基本信息','Save conference details')}}</ElButton><ElButton :disabled="saving" @click="reload">{{t('重新载入','Reload')}}</ElButton></div>
  </ElForm>
  <ElButton v-else @click="load">{{t('重新载入','Reload')}}</ElButton>
 </div>
</template>

<style scoped>
.basic-conference-editor{scroll-margin-top:24px;padding:26px 0 30px;border-bottom:1px solid #e5eaf0}.basic-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:15px;margin-bottom:24px}.basic-eyebrow{font-size:11px;letter-spacing:1.5px;color:#47809b;font-weight:700}.basic-heading h3{font-size:21px;margin:8px 0;color:#173b53}.basic-heading p{font-size:13px;line-height:1.7;color:#748393;margin:0}.basic-date-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.basic-date-grid :deep(.el-date-editor){width:100%}.basic-field-note{font-size:12px;color:#748393;line-height:1.7;margin:-8px 0 22px}.basic-field-note strong{color:#245a76}.basic-actions{display:flex;gap:10px;padding-top:5px}.basic-conference-editor :deep(.el-alert){margin-bottom:20px}@media(max-width:650px){.basic-date-grid{grid-template-columns:1fr;gap:0}.basic-heading{flex-direction:column}.basic-conference-editor{padding-top:20px}}
</style>

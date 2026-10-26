<script setup>
import {computed,onMounted,ref} from 'vue';
import {ElFormItem,ElInput,ElSelect,ElOption,ElAlert,ElButton} from 'element-plus';
import chinaRegions from './china-regions.json';

const props=defineProps({model:{type:Object,required:true},language:{type:String,default:'zh'},disabled:Boolean});
const t=(zh,en)=>props.language==='en'?en:zh;
const options=ref({subject_domains:[],planned_indexing:[],countries:[]}),error=ref(''),loading=ref(false);
// Source: modood/Administrative-divisions-of-China (license in china-regions.LICENSE); custom entries cover overseas and updates.
const regions={...chinaRegions,'北京市':['北京市'],'天津市':['天津市'],'上海市':['上海市'],'重庆市':['重庆市'],'香港特别行政区':['香港'],'澳门特别行政区':['澳门'],'台湾省':[]};
const provinces=computed(()=>props.model.country==='中国'?Object.keys(regions):[]);
const cities=computed(()=>props.model.country==='中国'?regions[props.model.province]||[]:[]);
const domainEnglish=['Mathematics','Physics & mechanics','Aerospace science','Earth sciences','Biology & bioengineering','Medicine & medical engineering','Artificial intelligence','Computer science & technology','Electronics & communication','Information & systems science','Information and systems engineering','Power & electrical engineering','Energy science','Environment & resource technology','Materials science','Metallurgical engineering','Mechanical engineering','Mining engineering','Civil & architectural engineering','Hydraulic engineering','Transportation engineering','Economics','Management','Arts','Sports science','Education','Sociology','Optics & optical engineering','Marine science & engineering','Surveying & mapping','Textile science','Safety science','Chemistry & chemical engineering','Agriculture & agricultural engineering','Animal husbandry & veterinary science','Food science','Nuclear science','Astronomy','Pharmacy & traditional Chinese medicine','Psychology','Political science','Law','History, literature & philosophy','Ethnicity & religion','Interdisciplinary studies'];
function countryChanged(){props.model.province='';props.model.city='';}
function provinceChanged(){props.model.city=cities.value.length===1?cities.value[0]:'';}
async function load(){
 loading.value=true;error.value='';
 try{const response=await fetch('/api/conferences/metadata-options',{credentials:'same-origin',cache:'no-store'});if(!response.ok)throw new Error();options.value=await response.json();}
 catch{error.value=t('领域与地区选项加载失败，请重新加载后继续。','Could not load subject and region choices. Reload to continue.');}
 finally{loading.value=false;}
}
onMounted(load);
</script>

<template>
 <div class="conference-metadata-fields">
  <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon><ElButton text @click="load">{{t('重新加载选项','Reload choices')}}</ElButton></ElAlert>
  <div class="metadata-two-cols">
   <ElFormItem :label="t('主办方名称','Organizer name')" prop="organizer_name" :rules="[{required:true,whitespace:true,message:t('请填写主办单位名称','Enter the organizer name'),trigger:'blur'}]"><ElInput v-model="model.organizer_name" name="organizer_name" :disabled="disabled" maxlength="200" :placeholder="t('请输入主办单位名称，例如：某某大学','Organizer institution, e.g. Example University')"/></ElFormItem>
   <ElFormItem :label="t('联系电话','Contact phone')" prop="organizer_phone" :rules="[{required:true,whitespace:true,message:t('请填写联系电话','Enter a contact phone number'),trigger:'blur'}]"><ElInput v-model="model.organizer_phone" name="organizer_phone" type="tel" :disabled="disabled" maxlength="100" :placeholder="t('供参会者、投稿专家及合作机构咨询会议安排','For participant, author and partner inquiries')"/></ElFormItem>
  </div>
  <ElFormItem :label="t('会议领域（可多选、删除）','Subject domains (multiple selections)')" prop="subject_domains"><ElSelect v-model="model.subject_domains" name="subject_domains" multiple filterable clearable :loading="loading" :disabled="disabled" :placeholder="t('选择会议涉及的学科领域','Select the conference subject domains')"><ElOption v-for="(item,index) in options.subject_domains" :key="item" :value="item" :label="language==='en'?domainEnglish[index]||item:item"/></ElSelect></ElFormItem>
  <div class="metadata-regions">
   <ElFormItem :label="t('国家/地区','Country / territory')" prop="country" :rules="[{required:true,whitespace:true,message:t('请选择国家/地区','Choose a country or territory'),trigger:'change'}]"><ElSelect v-model="model.country" name="country" filterable allow-create default-first-option :disabled="disabled" :placeholder="t('选择或输入国家/地区','Select or enter a country')" @change="countryChanged"><ElOption v-for="item in options.countries" :key="item.value" :value="item.value" :label="language==='en'?item.label_en:item.value"/></ElSelect></ElFormItem>
   <ElFormItem :label="t('省/州/地区','Province / state / region')" prop="province" :rules="[{required:true,whitespace:true,message:t('请选择或填写省/州/地区','Select or enter a province, state or region'),trigger:'change'}]"><ElSelect v-model="model.province" name="province" filterable allow-create default-first-option :disabled="disabled" :placeholder="t('选择或输入省/州','Select or enter a province')" @change="provinceChanged"><ElOption v-for="item in provinces" :key="item" :value="item" :label="item"/></ElSelect></ElFormItem>
   <ElFormItem :label="t('城市','City')" prop="city" :rules="[{required:true,whitespace:true,message:t('请选择或填写城市','Select or enter a city'),trigger:'change'}]"><ElSelect v-model="model.city" name="city" filterable allow-create default-first-option :disabled="disabled" :placeholder="t('选择或输入城市','Select or enter a city')"><ElOption v-for="item in cities" :key="item" :value="item" :label="item"/></ElSelect></ElFormItem>
  </div>
  <p class="metadata-note">{{t('支持搜索和自填；境外地区可输入省州与城市，不适用的层级可填“不适用”。输入后按回车确认。','Search or enter custom regions. For overseas locations, enter the state and city; use N/A where needed. Press Enter to confirm custom entries.')}}</p>
  <ElFormItem :label="t('详细地址','Detailed address')" prop="detail_address" :rules="[{required:true,whitespace:true,message:t('请填写详细地址，尚未确定可填“待定”','Enter the detailed address, or TBA if undecided'),trigger:'blur'}]"><ElInput v-model="model.detail_address" name="detail_address" :disabled="disabled" maxlength="500" :placeholder="t('填写场地、街道与门牌号；场地未确定可填“待定”','Venue and street address; enter TBA if undecided')"/></ElFormItem>
  <ElFormItem :label="t('会议计划检索（可多选、删除）','Planned indexing (multiple selections)')" prop="planned_indexing"><ElSelect v-model="model.planned_indexing" name="planned_indexing" multiple filterable clearable :loading="loading" :disabled="disabled" :placeholder="t('选择会议计划申请的检索数据库','Select the indexing databases planned for the conference')"><ElOption v-for="item in options.planned_indexing" :key="item" :value="item" :label="language==='en'?({'维普':'VIP','万方':'Wanfang','其它':'Other'}[item]||item):item"/></ElSelect></ElFormItem>
  <p class="metadata-note">{{t('此处记录会议计划申请的检索范围，实际收录结果以数据库审核与公布为准。','These are planned indexing targets. Actual inclusion depends on the database review and publication.')}}</p>
 </div>
</template>

<style scoped>
.metadata-two-cols{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 20px}.metadata-regions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 16px}.conference-metadata-fields :deep(.el-select){width:100%}.metadata-note{font-size:12px;line-height:1.7;color:#738293;margin:-9px 0 20px}.conference-metadata-fields :deep(.el-alert){margin-bottom:20px}@media(max-width:700px){.metadata-two-cols,.metadata-regions{grid-template-columns:1fr}}
</style>

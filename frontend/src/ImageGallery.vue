<script setup>
import {ref,nextTick} from 'vue';
import {ElButton,ElAlert} from 'element-plus';

const props=defineProps({modelValue:{type:Array,default:()=>[]},upload:{type:Function,required:true},disabled:Boolean,language:String,label:String});
const emit=defineEmits(['update:modelValue']);
const busy=ref(false),error=ref('');
const t=(zh,en)=>props.language==='en'?en:zh;
async function add(files){
 if(props.disabled||busy.value)return;
 const selected=Array.from(files||[]);if(!selected.length)return;
 error.value='';
 if(selected.length+props.modelValue.length>20){error.value=t('每组最多20张图片，请减少本次选择的数量。','Each gallery supports 20 images. Select fewer files.');return;}
 busy.value=true;
 try{
  for(const file of selected){const url=await props.upload(file);emit('update:modelValue',[...props.modelValue,url]);await nextTick();}
 }catch(e){error.value=e.message;}finally{busy.value=false;}
}
function choose(event){const files=Array.from(event.target.files||[]);event.target.value='';add(files);}
function paste(event){const files=Array.from(event.clipboardData?.files||[]);if(files.length){event.preventDefault();add(files);}}
function remove(index){emit('update:modelValue',props.modelValue.filter((_,i)=>i!==index));}
function move(index,offset){const result=[...props.modelValue];result.splice(index+offset,0,result.splice(index,1)[0]);emit('update:modelValue',result);}
</script>

<template>
 <div class="image-gallery" tabindex="0" :aria-label="label||t('图片上传区','Image upload area')" @dragover.prevent @drop.prevent="add($event.dataTransfer.files)" @paste="paste">
  <div class="gallery-heading"><strong>{{label||t('图片','Images')}} <small>{{modelValue.length}} / 20</small></strong><label class="gallery-upload"><input type="file" multiple accept="image/png,image/jpeg,image/webp" :disabled="disabled||busy" @change="choose"/><span>{{busy?t('上传中…','Uploading…'):t('批量上传图片','Upload images')}}</span></label></div>
  <p class="gallery-help">{{t('可选择多张、拖入或粘贴图片。每张不超过5 MiB，支持 PNG、JPEG、WebP；保存后生效。','Select multiple files, drop or paste images. PNG, JPEG or WebP, up to 5 MiB each. Save to apply.')}}</p>
  <ElAlert v-if="error" :title="error" type="error" :closable="false" show-icon/>
  <div v-if="modelValue.length" class="gallery-grid"><figure v-for="(url,index) in modelValue" :key="url+'-'+index"><img :src="url" :alt="`${label||t('图片','Image')} ${index+1}`"/><figcaption><ElButton :disabled="disabled||busy||index===0" :aria-label="t('图片前移','Move image earlier')" @click="move(index,-1)">←</ElButton><ElButton :disabled="disabled||busy||index===modelValue.length-1" :aria-label="t('图片后移','Move image later')" @click="move(index,1)">→</ElButton><ElButton type="danger" text :disabled="disabled||busy" @click="remove(index)">{{t('移除','Remove')}}</ElButton></figcaption></figure></div>
 </div>
</template>

<style scoped>
.image-gallery{border:1px dashed #b7cad7;border-radius:5px;padding:16px;margin:16px 0;min-width:0;background:#fafdff}.image-gallery:focus-visible{outline:2px solid #448fb3;outline-offset:2px}.gallery-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.gallery-heading strong{font-size:13px;color:#41647c}.gallery-heading small{font-weight:400;color:#7d8e9d;margin-left:8px}.gallery-upload{position:relative;display:inline-flex;padding:9px 13px;overflow:hidden;border:1px solid #bacbd7;border-radius:4px;color:#416d88;background:white;font-size:12px;cursor:pointer}.gallery-upload:focus-within{outline:2px solid #448fb3}.gallery-upload:has(input:disabled){opacity:.55;cursor:not-allowed}.gallery-upload input{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:inherit}.gallery-help{font-size:11px;color:#738896;line-height:1.7;margin:10px 0 0}.gallery-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:14px;margin-top:15px}.gallery-grid figure{margin:0;min-width:0;border:1px solid #e1e9ef;background:white;border-radius:4px;overflow:hidden}.gallery-grid img{width:100%;height:145px;object-fit:contain;display:block}.gallery-grid figcaption{display:flex;justify-content:center;flex-wrap:wrap;padding:7px;border-top:1px solid #edf1f5;gap:4px}.gallery-grid .el-button{margin:0;padding:6px 9px;height:auto;font-size:11px}.image-gallery .el-alert{margin-top:12px}@media(max-width:600px){.image-gallery{padding:12px}.gallery-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.gallery-grid img{height:100px}.gallery-grid figcaption{padding:5px;gap:2px}.gallery-grid .el-button{padding:5px 6px}}
</style>

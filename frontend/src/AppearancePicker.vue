<script setup>
import {ref,computed} from 'vue';
import {ElButton,ElDialog} from 'element-plus';

const props=defineProps({appearances:{type:Array,default:()=>[]},theme:{type:Object,required:true},disabled:Boolean,language:{type:String,default:'zh'},preview:{type:Function,required:true}});
const emit=defineEmits(['select']);
const t=(zh,en)=>props.language==='en'?en:zh;
const groups=computed(()=>[{layout:'simple-1',title:t('简约一 · 横向导航','Simple 1 · Horizontal navigation'),description:t('大横幅、横向导航与信息侧栏。','Large banner, horizontal navigation and information sidebar.')},{layout:'simple-2',title:t('简约二 · 左侧导航','Simple 2 · Left navigation'),description:t('左侧站点导航，右侧横幅与正文。','Site navigation on the left, banner and content on the right.')}]);
const selected=computed(()=>props.appearances.find(item=>item.layout===(props.theme.layout||'simple-1')&&item.accent.toLowerCase()===props.theme.accent?.toLowerCase()));
const open=ref(false),html=ref(''),mobile=ref(false),frame=ref(null);
function choose(item){if(!props.disabled)emit('select',item);}
async function showPreview(){
 if(props.disabled)return;
 try{
  const source=await props.preview();
  const doc=new DOMParser().parseFromString(source,'text/html');
  doc.querySelectorAll('base').forEach(base=>base.remove());
  const base=doc.createElement('base');base.href=window.location.origin+'/';doc.head.prepend(base);
  html.value='<!doctype html>'+doc.documentElement.outerHTML;mobile.value=false;open.value=true;
 }catch{}
}
function preventNavigation(){
 const doc=frame.value?.contentDocument;
 if(!doc)return;
 doc.addEventListener('click',event=>{if(event.target.closest?.('a')){event.preventDefault();event.stopImmediatePropagation();}},true);
 doc.addEventListener('submit',event=>event.preventDefault(),true);
}
function closePreview(){html.value='';open.value=false;}
</script>

<template>
 <section id="appearance-presets" class="surface appearance-picker" data-test="appearance-picker" :aria-label="t('预制外观','Appearance presets')">
  <div class="appearance-heading"><div><h3>{{t('预制外观','Appearance presets')}}</h3><p>{{t('选择布局与配色，保存首页设计后应用。会议内容与图片保持不变。','Choose a layout and color, then save the homepage to apply. Conference content and images are preserved.')}}</p></div><ElButton data-test="preview-appearance" :disabled="disabled" @click="showPreview">{{t('预览当前外观','Preview current appearance')}}</ElButton></div>
  <p class="appearance-current" aria-live="polite">{{selected?t('当前选择：','Selected: ')+(language==='en'?selected.name_en:selected.name):t('当前为自定义配色，未选择预制外观。','Custom accent color; no preset selected.')}}</p>
  <fieldset v-for="group in groups" :key="group.layout" class="appearance-group" data-test="appearance-group" :disabled="disabled"><legend>{{group.title}}</legend><p>{{group.description}}</p><div class="appearance-grid">
   <label v-for="item in appearances.filter(item=>item.layout===group.layout)" :key="item.id" class="appearance-card" :class="{'is-selected':selected?.id===item.id}" :style="{'--preview-accent':item.accent}">
    <input type="radio" name="conference-appearance" :data-test="`appearance-${item.id}`" :value="item.id" :checked="selected?.id===item.id" :disabled="disabled" :aria-label="language==='en'?item.name_en:item.name" @change="choose(item)"/>
    <svg class="appearance-thumbnail" viewBox="0 0 280 174" aria-hidden="true" focusable="false">
     <rect width="280" height="174" fill="#f2f5f8"/><rect width="280" height="12" fill="#fff"/><rect x="9" y="4" width="45" height="4" rx="1" fill="#24465e"/><rect x="240" y="4" width="30" height="3" fill="#bacbd7"/>
     <template v-if="item.layout==='simple-1'">
      <rect y="12" width="280" height="53" fill="#173956"/><path d="M190 12H280V65H140Z" fill="#244b68"/><rect x="18" y="27" width="150" height="6" fill="#fff"/><rect x="18" y="39" width="98" height="3" fill="#b7cddd"/><rect x="18" y="49" width="57" height="4" fill="var(--preview-accent)"/>
      <rect y="65" width="280" height="15" fill="#fff"/><rect x="13" y="65" width="35" height="15" fill="var(--preview-accent)"/><path d="M58 72H86M98 72H126M138 72H166M178 72H206" stroke="#9cabb7" stroke-width="3"/>
      <rect x="12" y="89" width="169" height="72" fill="#fff"/><rect x="20" y="97" width="3" height="9" fill="var(--preview-accent)"/><rect x="29" y="99" width="55" height="4" fill="#31556e"/><path d="M20 115H170M20 122H170M20 129H146" stroke="#d6dfe6" stroke-width="3"/><rect x="20" y="140" width="43" height="12" rx="1" fill="var(--preview-accent)"/>
      <rect x="190" y="89" width="78" height="35" fill="#fff"/><rect x="198" y="97" width="40" height="4" fill="var(--preview-accent)"/><path d="M198 109H259M198 116H245" stroke="#d6dfe6" stroke-width="3"/><rect x="190" y="131" width="78" height="30" fill="#fff"/><rect x="198" y="138" width="40" height="4" fill="var(--preview-accent)"/><path d="M198 150H259" stroke="#d6dfe6" stroke-width="3"/>
     </template>
     <template v-else>
      <rect y="12" width="65" height="152" fill="#fff"/><rect x="8" y="25" width="48" height="5" fill="#31556e"/><rect y="40" width="65" height="17" fill="var(--preview-accent)"/><path d="M12 48H47" stroke="#fff" stroke-width="3"/><path d="M12 67H49M12 85H49M12 103H49M12 121H49" stroke="#a7b7c3" stroke-width="3"/>
      <rect x="65" y="12" width="215" height="53" fill="#173956"/><path d="M232 12H280V65H190Z" fill="#244b68"/><rect x="79" y="27" width="147" height="6" fill="#fff"/><rect x="79" y="39" width="98" height="3" fill="#b7cddd"/><rect x="79" y="49" width="57" height="4" fill="var(--preview-accent)"/>
      <rect x="75" y="75" width="195" height="57" fill="#fff"/><rect x="83" y="83" width="3" height="9" fill="var(--preview-accent)"/><rect x="92" y="85" width="55" height="4" fill="#31556e"/><path d="M83 101H260M83 108H260M83 115H219" stroke="#d6dfe6" stroke-width="3"/>
      <rect x="75" y="140" width="93" height="24" fill="#fff"/><rect x="176" y="140" width="94" height="24" fill="#fff"/><rect x="83" y="146" width="48" height="4" fill="var(--preview-accent)"/><rect x="184" y="146" width="48" height="4" fill="var(--preview-accent)"/><path d="M83 156H157M184 156H258" stroke="#d6dfe6" stroke-width="3"/>
     </template>
     <rect y="169" width="280" height="5" fill="#173956"/>
    </svg>
    <span class="appearance-card-caption"><span class="appearance-swatch"/><span>{{language==='en'?item.name_en:item.name}}</span><span v-if="selected?.id===item.id" class="appearance-check" aria-hidden="true">✓</span></span>
   </label>
  </div></fieldset>
  <p class="appearance-footnote">{{t('缩略图展示布局示意。实际预览使用当前已保存的会议内容；未保存的文字和图片不会显示。','Thumbnails illustrate the layouts. Preview uses saved conference content; unsaved text and images are not shown.')}}</p>
  <ElDialog v-model="open" :title="t('会议外观预览','Conference appearance preview')" width="min(1200px, 96vw)" top="3vh" append-to-body destroy-on-close data-test="appearance-preview-dialog" @closed="closePreview">
   <div class="appearance-preview-tools"><p>{{t('仅预览当前页面，页面链接已停用。未保存的文字和图片不会显示。','This page only; links are disabled. Unsaved text and images are not shown.')}}</p><div><ElButton :type="!mobile?'primary':'default'" :aria-pressed="!mobile" @click="mobile=false">{{t('桌面视图','Desktop view')}}</ElButton><ElButton :type="mobile?'primary':'default'" :aria-pressed="mobile" @click="mobile=true">{{t('手机视图','Mobile view')}}</ElButton></div></div>
   <div class="appearance-preview-stage"><iframe v-if="html" ref="frame" data-test="appearance-preview-frame" :title="t('当前外观的会议页面预览','Conference page in the current appearance')" :srcdoc="html" sandbox="allow-scripts allow-same-origin" :class="{'is-mobile':mobile}" @load="preventNavigation"/></div>
   <template #footer><ElButton @click="open=false">{{t('关闭预览','Close preview')}}</ElButton></template>
  </ElDialog>
 </section>
</template>

<style scoped>
.appearance-picker{padding:26px;min-width:0}.appearance-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:18px}.appearance-heading h3{margin:0 0 8px;color:#24465e;font-size:16px;font-weight:600}.appearance-heading p,.appearance-group>p,.appearance-footnote,.appearance-current{font-size:12px;line-height:1.8;color:#637d90;margin:0}.appearance-heading>.el-button{flex-shrink:0}.appearance-current{margin-top:14px;color:#344f65}.appearance-group{border:0;padding:0;margin:24px 0 0;min-width:0}.appearance-group legend{font-size:14px;font-weight:600;color:#24465e;padding:0;margin-bottom:4px}.appearance-group>p{margin-bottom:12px}.appearance-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.appearance-card{display:block;position:relative;border:1px solid #dce5ec;border-radius:5px;overflow:hidden;cursor:pointer;background:#fff;min-width:0}.appearance-card:hover{border-color:#7896ac}.appearance-card.is-selected{border-color:#2c718f;box-shadow:0 0 0 1px #2c718f}.appearance-card:focus-within{outline:3px solid #2c718f;outline-offset:3px}.appearance-card:has(input:disabled){opacity:.6;cursor:not-allowed}.appearance-card input{position:absolute;width:1px;height:1px;opacity:0}.appearance-thumbnail{display:block;width:100%;height:auto;border-bottom:1px solid #e5ebef}.appearance-card-caption{display:flex;align-items:center;gap:8px;padding:11px 12px;font-size:12px;color:#344f65;min-height:40px;box-sizing:border-box}.appearance-swatch{background:var(--preview-accent);width:12px;height:12px;border-radius:50%;flex-shrink:0}.appearance-check{margin-left:auto;color:#2c718f;font-weight:700}.appearance-footnote{margin:18px 0 0}.appearance-preview-tools{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}.appearance-preview-tools p{font-size:12px;line-height:1.7;color:#637d90;margin:0}.appearance-preview-tools>div{display:flex;flex-shrink:0;gap:8px}.appearance-preview-tools .el-button+.el-button{margin-left:0}.appearance-preview-stage{overflow:auto;background:#e9eef2;padding:12px;max-width:100%;box-sizing:border-box}.appearance-preview-stage iframe{display:block;background:#fff;border:0;width:1100px;max-width:none;height:68vh;margin:auto}.appearance-preview-stage iframe.is-mobile{width:390px}
@media(max-width:750px){.appearance-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.appearance-heading{flex-direction:column}.appearance-preview-tools{flex-direction:column;align-items:flex-start}}
@media(max-width:600px){.appearance-picker{padding:18px}.appearance-grid{gap:10px}.appearance-card-caption{padding:9px 8px;gap:5px;font-size:11px}.appearance-heading h3{font-size:14px}.appearance-group{margin-top:20px}.appearance-preview-stage{padding:6px}}
</style>

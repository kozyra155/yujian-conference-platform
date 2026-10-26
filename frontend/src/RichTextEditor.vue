<script setup>
import {ref,onMounted,watch} from 'vue';
import {ElButton} from 'element-plus';

const props=defineProps({modelValue:{type:String,default:''},disabled:Boolean,language:String});
const emit=defineEmits(['update:modelValue']);
const editor=ref();
const t=(zh,en)=>props.language==='en'?en:zh;
const update=()=>emit('update:modelValue',editor.value.innerText.trim()?editor.value.innerHTML:editor.value.querySelector('table')?editor.value.innerHTML:'');
onMounted(()=>{editor.value.innerHTML=props.modelValue;});
watch(()=>props.modelValue,value=>{if(editor.value&&editor.value.innerHTML!==value&&document.activeElement!==editor.value)editor.value.innerHTML=value;});
function command(name){if(props.disabled)return;editor.value.focus();document.execCommand(name,false);update();}
function insert(node){
 if(props.disabled)return;editor.value.focus();const selection=window.getSelection();
 const range=selection.rangeCount&&editor.value.contains(selection.anchorNode)?selection.getRangeAt(0):document.createRange();
 if(!editor.value.contains(range.commonAncestorContainer)){range.selectNodeContents(editor.value);range.collapse(false);}
 range.deleteContents();range.insertNode(node);range.setStartAfter(node);range.collapse(true);selection.removeAllRanges();selection.addRange(range);update();
}
function table(){
 const node=document.createElement('table');
 for(let r=0;r<3;r++){const row=node.insertRow();for(let c=0;c<2;c++){const cell=r===0?document.createElement('th'):document.createElement('td');cell.textContent=r===0?t('标题','Heading'):t('内容','Content');row.append(cell);}}
 insert(node);
}
function paste(event){event.preventDefault();insert(document.createTextNode(event.clipboardData.getData('text/plain')));}
</script>

<template>
 <div class="rich-editor" :class="{'is-disabled':disabled}">
  <div class="rich-tools" role="toolbar" :aria-label="t('内容格式','Text formatting')" @mousedown.prevent>
   <ElButton :disabled="disabled" @click="command('bold')">{{t('加粗','Bold')}}</ElButton><ElButton :disabled="disabled" @click="command('italic')">{{t('斜体','Italic')}}</ElButton><ElButton :disabled="disabled" @click="command('insertUnorderedList')">{{t('项目列表','Bullet list')}}</ElButton><ElButton :disabled="disabled" @click="table">{{t('插入表格','Insert table')}}</ElButton><ElButton :disabled="disabled" @click="command('removeFormat')">{{t('清除格式','Clear formatting')}}</ElButton>
  </div>
  <div ref="editor" class="rich-input" :contenteditable="!disabled" role="textbox" aria-multiline="true" :aria-label="t('详细联系信息','Detailed contact information')" :aria-invalid="modelValue.length>20000" @input="update" @paste="paste" @drop.prevent></div>
  <p :class="{'rich-over-limit':modelValue.length>20000}">{{t('支持文字排版与表格；图片可在下方批量添加。内容含格式最多20000字符。','Format text and tables; add images below. Maximum 20,000 characters including formatting.')}} {{modelValue.length}} / 20000</p>
 </div>
</template>

<style scoped>
.rich-editor{min-width:0;border:1px solid #dce4ec;border-radius:4px;overflow:hidden;margin:10px 0 16px;background:white}.rich-tools{display:flex;flex-wrap:wrap;gap:6px;padding:9px;background:#f5f8fb;border-bottom:1px solid #dce4ec}.rich-tools .el-button{height:auto;padding:7px 9px;font-size:11px;margin:0}.rich-input{min-height:150px;max-height:450px;overflow:auto;padding:14px;font-size:14px;line-height:1.8;overflow-wrap:anywhere}.rich-input:focus{outline:2px solid #448fb3;outline-offset:-2px}.rich-input :deep(table){border-collapse:collapse;width:100%;margin:10px 0}.rich-input :deep(td),.rich-input :deep(th){border:1px solid #c6d3dd;padding:8px;min-width:50px}.rich-editor>p{font-size:11px;color:#748997;margin:0;padding:9px 13px;border-top:1px solid #edf1f5;line-height:1.6}.rich-editor>p.rich-over-limit{color:#b54040}.is-disabled{opacity:.7}
</style>

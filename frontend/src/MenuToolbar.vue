<script setup>
import {ref,onMounted,onUnmounted,computed} from 'vue';
import {ElConfigProvider,ElInput,ElButton,ElIcon,ElRadioGroup,ElRadioButton,ElDropdown,ElDropdownMenu,ElDropdownItem} from 'element-plus';
import {Search,Plus,ArrowDown,Sort,Document} from '@element-plus/icons-vue';
import zhCn from 'element-plus/es/locale/lang/zh-cn';
import en from 'element-plus/es/locale/lang/en';
const language=ref(window.MeetPortal?.language||'zh'),category=ref('website'),query=ref('');
const counts=ref({website:0,functions:0,all:0,matched:0});
const root=document.querySelector('#meet-menu-editor');
const locked=root.dataset.locked==='true',enabled=root.dataset.enabled==='true';
const t=(zh,en)=>language.value==='en'?en:zh;
const locale=computed(()=>language.value==='en'?en:zhCn);
function filter(){window.dispatchEvent(new CustomEvent('meet-menu-filter',{detail:{category:category.value,query:query.value}}));}
function add(type){document.querySelector(`.meet-editor-native-content .add-${type}`)?.click();}
function order(){category.value='all';query.value='';filter();}
function update(event){counts.value=event.detail;}
function lang(event){language.value=event.detail.language;}
onMounted(()=>{window.addEventListener('meet-menu-counts',update);window.addEventListener('meet-language-change',lang);filter();});
onUnmounted(()=>{window.removeEventListener('meet-menu-counts',update);window.removeEventListener('meet-language-change',lang);});
</script>
<template>
 <ElConfigProvider :locale="locale"><div class="meet-toolbar-heading"><div><h2>{{t('网站栏目','Website sections')}}<span>{{counts.all}}</span></h2><p>{{t('管理导航与页面内容，修改后自动保存排列。','Manage navigation and content. Order changes are saved automatically.')}}</p></div><ElDropdown v-if="enabled&&!locked" trigger="click" @command="add"><ElButton type="primary" :icon="Plus">{{t('添加栏目','Add section')}}<ElIcon class="el-icon--right"><ArrowDown/></ElIcon></ElButton><template #dropdown><ElDropdownMenu><ElDropdownItem command="page">{{t('新建内容页面','New content page')}}</ElDropdownItem><ElDropdownItem command="link">{{t('添加外部链接','External link')}}</ElDropdownItem><ElDropdownItem command="separator">{{t('添加分隔线','Separator')}}</ElDropdownItem></ElDropdownMenu></template></ElDropdown></div>
 <div class="meet-toolbar-filters"><ElRadioGroup v-model="category" @change="filter" :aria-label="t('栏目分类','Section category')"><ElRadioButton value="website">{{t('网站栏目','Website')}} <span>{{counts.website}}</span></ElRadioButton><ElRadioButton value="functions">{{t('会务功能','Conference tools')}} <span>{{counts.functions}}</span></ElRadioButton><ElRadioButton value="all">{{t('全部','All')}} <span>{{counts.all}}</span></ElRadioButton></ElRadioGroup><ElInput v-model="query" :prefix-icon="Search" clearable :placeholder="t('搜索栏目名称','Search section titles')" :aria-label="t('搜索栏目','Search sections')" @input="filter" @clear="filter"/></div>
 <div class="meet-toolbar-hint"><span><ElIcon><Document/></ElIcon>{{t('显示','Showing')}} {{counts.matched}} {{t('项','sections')}}</span><ElButton v-if="enabled&&!locked&&(category!=='all'||query)" text :icon="Sort" @click="order">{{t('调整顺序','Reorder sections')}}</ElButton><span v-else-if="enabled&&!locked" class="meet-sort-hint">{{t('拖动栏目左侧手柄即可排序','Drag the handle at the left to reorder')}}</span></div></ElConfigProvider>
</template>

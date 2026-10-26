import {createApp} from 'vue';
import App from './App.vue';
import MenuToolbar from './MenuToolbar.vue';
import 'element-plus/dist/index.css';
import './workspace.css';
const root=document.querySelector('#meet-workspace');
if(root)createApp(App,{mode:root.dataset.mode,eventId:Number(root.dataset.eventId)||null,financeAdmin:root.dataset.financeAdmin==='true'}).mount(root);
const editor=document.querySelector('#meet-menu-toolbar');
if(editor)createApp(MenuToolbar).mount(editor);

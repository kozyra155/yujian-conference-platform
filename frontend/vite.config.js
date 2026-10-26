import {defineConfig} from 'vite';
import vue from '@vitejs/plugin-vue';
export default defineConfig({
 plugins:[vue()],
 base:'/portal-assets/ui-dist/',
 build:{outDir:'../portal/ui-dist',emptyOutDir:true,rollupOptions:{input:'src/main.js',output:{entryFileNames:'workspace.js',assetFileNames:'workspace.[ext]'}}}
});

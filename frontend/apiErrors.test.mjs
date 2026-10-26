import assert from 'node:assert/strict';
import {errorMessage} from './src/apiErrors.js';

assert.equal(errorMessage({error:{message:'单位网址：请使用 https:// 链接。'}},'failed'),'单位网址：请使用 https:// 链接。');
assert.equal(errorMessage({message:'标题过长'},'failed'),'标题过长');
assert.equal(errorMessage({error:'Invalid image'},'failed'),'Invalid image');
for(const data of [null,[],{}, {error:{traceback:'secret'}},{message:{}},{message:'   '}]){
 assert.equal(errorMessage(data,'操作失败，草稿已保留。'),'操作失败，草稿已保留。');
}
console.log('API error messages: passed');

/* Deterministic settings queue tests. No browser, real library or filesystem mutation. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const core=require('../assets/workspace-core.js');
const source=fs.readFileSync(path.join(__dirname,'../assets/settings.js'),'utf8');
const turn=()=>new Promise(resolve=>setImmediate(resolve));
function fixture(){
  const fields={}, pending=[], records={};
  const defaults=()=>({folder_id:null,tags:[],hierarchy:false,auto_export:true});
  const libraries={A:{id:'A',import_options:defaults()},B:{id:'B',import_options:defaults()}};
  records.A=defaults();records.B=defaults();
  const $=id=>fields[id]||(fields[id]={value:'',checked:false,disabled:false,open:true,textContent:'',
    setAttribute(){},addEventListener(){},focus(){},close(){this.open=false}});
  $('setting-library').value='A';
  const context={$,core,lib:id=>libraries[id],manualOptions:()=>[],options:(select,items,value)=>{select.value=value||''},
    tags:s=>s.split(',').map(s=>s.trim()).filter(Boolean),bind(){},toast(){},
    window:{addEventListener(){}},document:{addEventListener(){},activeElement:{blur(){}}},
    api:(route,body)=>new Promise(resolve=>{const snapshot=JSON.parse(JSON.stringify(body));pending.push(()=>{records[snapshot.library_id]=snapshot.options;resolve(snapshot.options)})})};
  vm.createContext(context);
  vm.runInContext(source+'\nthis.ops={saveImportSetting,closeSettings,fillSettingsLibrary};',context);
  context.ops.fillSettingsLibrary();
  async function drain(){for(let i=0;i<10;i++){await turn();if(!pending.length)break;pending.shift()()}await turn()}
  return {$,context,records,libraries,pending,drain};
}
async function finalValueWins(){
  const f=fixture();
  f.$('setting-tags').value='temporary';
  f.context.ops.saveImportSetting();
  await turn();
  f.$('setting-tags').value='';
  const close=f.context.ops.closeSettings();
  await f.drain();await close;
  assert.deepEqual(Array.from(f.records.A.tags),[],'closing must persist the final empty value after the earlier in-flight request');
  assert.equal(f.$('settings-dialog').open,false);
}
async function switchKeepsVisibleOwnership(){
  const f=fixture();
  f.$('setting-tags').value='A pending';f.context.ops.saveImportSetting();await turn();
  f.$('setting-library').value='B';
  const switched=f.$('setting-library').onchange();
  try{
    assert.equal(f.$('setting-library').value,'A','visible owner must remain A until A is saved');
    assert.equal(f.$('setting-tags').disabled,true,'disable edits while switching libraries');
  }finally{await f.drain();await switched}
  assert.equal(f.$('setting-library').value,'B');
  assert.equal(f.$('setting-tags').disabled,false);
  assert.deepEqual(Array.from(f.records.A.tags),['A pending']);
  assert.deepEqual(Array.from(f.records.B.tags),[]);
}
(async()=>{let failed=0;for(const test of [finalValueWins,switchKeepsVisibleOwnership]){try{await test();console.log('PASS '+test.name)}catch(error){failed++;console.error('FAIL '+test.name+': '+error.message)}}process.exitCode=failed?1:0})();

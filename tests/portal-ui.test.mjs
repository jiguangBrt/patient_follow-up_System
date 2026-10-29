import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';
const source=readFileSync(new URL('../src/patient_follow_up_system/web/intake.js',import.meta.url),'utf8').replace(/init\(\);\s*$/,'');
function setup({stored={},blocked=false,sessionBlocked=false,fetcher=async()=>new Response('{}')}={}){
  const elements=new Map();
  const make=id=>({id,value:'',checked:false,required:false,disabled:false,textContent:'',className:'',files:[],classList:{values:new Set(),add(x){this.values.add(x);},remove(x){this.values.delete(x);},toggle(x,v){if(v)this.values.add(x);else this.values.delete(x);},contains(x){return this.values.has(x);}},setAttribute(){},removeAttribute(){},replaceChildren(){},querySelectorAll(){return[];},append(){},reset(){},showModal(){},close(){}});
  const element=id=>{if(!elements.has(id))elements.set(id,make(id));return elements.get(id);};
  const local=new Map(Object.entries(stored));let scrolls=0;
  const context=vm.createContext({console,URLSearchParams,crypto:webcrypto,Uint8Array,Date,Map,JSON,Response,Error,setTimeout,btoa:input=>Buffer.from(input,'binary').toString('base64'),URL:{revokeObjectURL(){},createObjectURL(){return'blob:test';}},location:{hash:'#token=public-qr-token-123456789',pathname:'/patientfollowup/intake',reload(){}},history:{replaceState(){}},localStorage:{getItem(key){if(blocked)throw Error();return local.get(key);},setItem(key,value){if(blocked)throw Error();local.set(key,value);},removeItem(key){local.delete(key);}},AppPaths:{url:p=>'/patientfollowup'+p,storage:{getItem(){if(sessionBlocked)throw Error();return null;},setItem(){if(sessionBlocked)throw Error();}},fetch:fetcher},document:{getElementById:element,querySelectorAll(){return[];},createElement:make},window:{scrollTo(){scrolls++;},addEventListener(){}},GastritisForms:{render:async()=>({read:()=>({})})}});
  vm.runInContext(source,context);return{context,element,local,run:s=>vm.runInContext(s,context),scrolls:()=>scrolls};
}
test('doctor namespace persists private token while restricted storage keeps current session usable',()=>{
 const ui=setup();ui.run("entry={doctor_id:4};storageSet(privateKey(),'private-four')");assert.equal(ui.local.get('patient-portal:/patientfollowup/:doctor:4'),'private-four');
 ui.run('entry={doctor_id:5}');assert.equal(ui.run('storageGet(privateKey())'),undefined);
 const limited=setup({blocked:true});limited.run("entry={doctor_id:4};storageSet(privateKey(),'session-secret')");assert.equal(limited.run('storageGet(privateKey())'),'session-secret');assert.equal(limited.run('storageWarning'),true);
});
test('first visit navigation always requests basic profile and does not fetch private records',async()=>{
 let requests=0;const ui=setup({fetcher:()=>{requests++;throw Error('unexpected');}});await ui.run("go('records')");assert.equal(ui.element('pageTitle').textContent,'我的');assert.equal(requests,0);
});
test('registration retries retain private idempotency key and only save token after successful response',async()=>{
 const calls=[];let first=true;
 const ui=setup({fetcher:async(path,options)=>{calls.push({path,options,body:JSON.parse(options.body||'{}')});if(first){first=false;return new Response('{"detail":"暂时失败"}',{status:503});}return new Response(JSON.stringify({access_token:'private-patient',patient:{display_name:'虚构人'},profile:{display_name:'虚构人',sex:'女',date_of_birth:'1990-01-01'},doctor_name:'测试医生'}));}});
 ui.run('entry={doctor_id:8,doctor_name:"测试医生"};currentNotice={id:2}');ui.element('displayName').value='虚构人';ui.element('sex').value='女';ui.element('dateOfBirth').value='1990-01-01';ui.element('registerConsent').checked=true;ui.element('relationship').value='本人';
 await ui.element('profileForm').onsubmit({preventDefault(){}});assert.equal(ui.run('accessToken'),null);await ui.element('profileForm').onsubmit({preventDefault(){}});
 assert.equal(calls[0].body.registration_key,calls[1].body.registration_key);assert.ok(calls[1].body.registration_key.length>=32);assert.equal(calls[1].options.headers.Authorization,undefined);assert.equal(ui.run('accessToken'),'private-patient');assert.equal(ui.element('pageTitle').textContent,'首页');
});
test('upload rejects oversize before reading file and keeps upload button recoverable',async()=>{
 const ui=setup();ui.element('uploadConsent').checked=true;ui.element('document').files=[{name:'huge.png',type:'image/png',size:9*1024*1024,arrayBuffer(){throw Error('must not read');}}];await ui.element('uploadForm').onsubmit({preventDefault(){}});assert.match(ui.element('status').textContent,/8 MB/);assert.equal(ui.element('uploadButton').disabled,false);
});
test('slow document response cannot overwrite a later navigation',async()=>{
 let resolve;const pending=new Promise(r=>resolve=r);const ui=setup({fetcher:()=>pending});ui.run("accessToken='private';entry={doctor_id:1}");const first=ui.run("go('records')");await ui.run("go('me')");resolve(new Response('[]'));await first;assert.equal(ui.element('pageTitle').textContent,'我的');assert.equal(ui.element('documentList').textContent,'正在读取…');
});
const prefix='patient-portal:/patientfollowup/:doctor:7';
const noticeResponse={id:1,title:'测试须知',version:'v1',content:'测试内容'};
function initializationFetcher({kind='public',binding=null,meStatus=200,meBinding='A'}={}){
 return async(path)=>{
  if(path==='/portal/entry')return new Response(JSON.stringify({doctor_id:7,doctor_name:'虚构医生',kind,target_binding:binding}));
  if(path==='/patient-notices/current')return new Response(JSON.stringify(noticeResponse));
  if(path==='/portal/me')return meStatus===200?new Response(JSON.stringify({patient:{id:1,display_name:'虚构甲'},profile:{},target_binding:meBinding})):new Response('{"detail":"凭据失效"}',{status:meStatus});
  throw Error('unexpected request '+path);
 };
}
test('sessionStorage and localStorage disabled at script startup do not crash entry token handling',async()=>{
 const ui=setup({blocked:true,sessionBlocked:true,fetcher:initializationFetcher()});await ui.run('init()');assert.equal(ui.element('pageTitle').textContent,'我的');assert.equal(ui.run('storageWarning'),true);assert.equal(ui.run('intakeToken'),'public-qr-token-123456789');
});
test('same doctor different patient QR blocks every private view until explicit logout',async()=>{
 const ui=setup({stored:{[prefix]:'private-A'},fetcher:initializationFetcher({kind:'patient',binding:'B',meBinding:'A'})});await ui.run('init()');
 assert.equal(ui.run('recoveryRequired'),true);assert.equal(ui.element('profileForm').classList.contains('hidden'),true);assert.match(ui.element('status').textContent,/二维码与本机档案不同/);await ui.run("go('records')");assert.equal(ui.element('pageTitle').textContent,'我的');assert.equal(ui.local.get(prefix),'private-A');
});
test('expired private access leaves persistent marker blocking public re-enrollment after refresh',async()=>{
 const ui=setup({stored:{[prefix]:'expired',[prefix+':registration']:'old-key'},fetcher:initializationFetcher({meStatus:401})});await ui.run('init()');
 assert.equal(ui.local.get(prefix),undefined);assert.equal(ui.local.get(prefix+':registration'),undefined);assert.equal(ui.local.get(prefix+':recovery'),'required');assert.equal(ui.element('profileForm').classList.contains('hidden'),true);
 const refreshed=setup({stored:Object.fromEntries(ui.local),fetcher:initializationFetcher()});await refreshed.run('init()');assert.equal(refreshed.run('recoveryRequired'),true);assert.equal(refreshed.element('profileForm').classList.contains('hidden'),true);
 await refreshed.element('profileForm').onsubmit({preventDefault(){}});assert.match(refreshed.element('status').textContent,/个人恢复二维码/);
});
test('personal QR permits recovery after expired bearer and clears marker only after successful registration',async()=>{
 const base=initializationFetcher({kind:'patient',binding:'A',meStatus:401});let registrations=0;
 const ui=setup({stored:{[prefix]:'expired'},fetcher:async(path,options)=>{
   if(path==='/portal/register'){registrations++;return new Response(JSON.stringify({access_token:'recovered',patient:{display_name:'虚构甲'},profile:{},target_binding:'A'}));}return base(path,options);
 }});await ui.run('init()');assert.equal(ui.element('profileForm').classList.contains('hidden'),false);assert.equal(ui.run('recoveryRequired'),false);assert.equal(ui.local.get(prefix+':recovery'),'required');
 ui.element('registerConsent').checked=true;ui.element('displayName').value='虚构甲';ui.element('sex').value='女';ui.element('dateOfBirth').value='1990-01-01';
 await ui.element('profileForm').onsubmit({preventDefault(){}});assert.equal(registrations,1);assert.equal(ui.local.get(prefix+':recovery'),undefined);assert.equal(ui.local.get(prefix),'recovered');assert.equal(ui.element('pageTitle').textContent,'首页');
});
test('persistent recovery marker accepts a new personal QR without stale private bearer',async()=>{
 const ui=setup({stored:{[prefix+':recovery']:'required'},fetcher:initializationFetcher({kind:'patient',binding:'A'})});await ui.run('init()');assert.equal(ui.run('recoveryRequired'),false);assert.equal(ui.element('profileForm').classList.contains('hidden'),false);assert.equal(ui.element('saveProfile').textContent,'保存并进入档案');
});

test('personal QR prefills and locks doctor-set name through registration and profile reload',async()=>{
 const base=initializationFetcher({kind:'patient',binding:'A'});let submitted;
 const ui=setup({fetcher:async(path,options)=>{
  if(path==='/portal/entry')return new Response(JSON.stringify({doctor_id:7,kind:'patient',target_binding:'A',locked_name:'医生设定姓名'}));
  if(path==='/portal/register'){submitted=JSON.parse(options.body);return new Response(JSON.stringify({access_token:'private',patient:{display_name:'医生设定姓名'},profile:{},target_binding:'A'}));}
  return base(path,options);
 }});
 await ui.run('init()');assert.equal(ui.element('displayName').value,'医生设定姓名');assert.equal(ui.element('displayName').readOnly,true);
 ui.element('displayName').value='浏览器自动填入其他姓名';ui.element('registerConsent').checked=true;
 await ui.element('profileForm').onsubmit({preventDefault(){}});
 assert.equal(submitted.display_name,'医生设定姓名');assert.equal(ui.element('displayName').value,'医生设定姓名');assert.equal(ui.element('status').textContent,'');assert.equal(ui.element('pageTitle').textContent,'首页');
});

test('public QR keeps name editable without a prefilled patient',async()=>{
 const ui=setup({fetcher:initializationFetcher()});await ui.run('init()');assert.equal(ui.element('displayName').value,'');assert.equal(ui.element('displayName').readOnly,false);
});

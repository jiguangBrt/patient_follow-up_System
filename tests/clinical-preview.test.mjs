import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source=readFileSync(new URL("../src/patient_follow_up_system/web/clinical.js",import.meta.url),"utf8");
const helpers=source.slice(source.indexOf("function setPreviewState("),source.indexOf("async function open("));
function setup(fetch) {
  const elements=new Map();
  const $=id=>{
    if(!elements.has(id)){
      const classes=new Set();
      elements.set(id,{textContent:"",style:{},attributes:{},classList:{
        add:name=>classes.add(name),contains:name=>classes.has(name),
        toggle:(name,on)=>on?classes.add(name):classes.delete(name),
      },setAttribute(name,value){this.attributes[name]=value;},removeAttribute(name){delete this[name];}});
    }
    return elements.get(id);
  };
  const urls=[],revoked=[],logouts=[];
  const sandbox={$,
    AppPaths:{fetch},AppSession:{logout:(...args)=>logouts.push(args)},
    URL:{createObjectURL:blob=>{const url=`blob:${blob.page}`;urls.push(url);return url;},revokeObjectURL:url=>revoked.push(url)},
    resizePreview(){},
  };
  vm.createContext(sandbox);
  vm.runInContext('let previewSequence=0,previewUrl=null;const current={id:7},token="fixture",staffRole="student";'+helpers,sandbox);
  return {$,sandbox,urls,revoked,logouts};
}
const response=page=>({ok:true,blob:async()=>({page})});

test("preview stays hidden through fetch and image decode; loading is inside the image area",async()=>{
  let resolve;
  const {$,sandbox}=setup(()=>new Promise(r=>{resolve=r;}));
  const pending=sandbox.preview(1);
  assert.ok($("previewWrap").classList.contains("hidden"));
  assert.match($("previewStatus").textContent,/正在加载/);
  assert.equal($("previewStage").attributes["aria-busy"],"true");
  assert.equal($("preview").src,undefined);
  resolve(response(1));await pending;
  assert.ok($("previewWrap").classList.contains("hidden"));
  $("preview").onload();
  assert.ok(!$("previewWrap").classList.contains("hidden"));
  assert.ok($("previewStatus").classList.contains("hidden"));
  assert.equal($("previewStage").attributes["aria-busy"],"false");
});

for(const failure of ["http","network","body","decode"]){
  test(`preview ${failure} failure shows an in-place message with no broken image`,async()=>{
    const {$,sandbox,revoked}=setup(async()=>{
      if(failure==="http")return {ok:false,status:503};
      if(failure==="network")throw new TypeError("offline");
      if(failure==="body")return {ok:true,blob:async()=>{throw new TypeError("disconnected");}};
      return response(1);
    });
    await sandbox.preview(1);
    if(failure==="decode")$("preview").onerror();
    assert.ok($("previewWrap").classList.contains("hidden"));
    assert.equal($("preview").src,undefined);
    assert.match($("previewStatus").textContent,/无法加载/);
    assert.equal($("previewStage").attributes["aria-busy"],"false");
    if(failure==="decode")assert.deepEqual(revoked,["blob:1"]);
  });
}

test("changing pages clears the old image and ignores stale decode events and HTTP responses",async()=>{
  let resolve;
  const {$,sandbox,revoked,urls}=setup(async path=>path.endsWith("/2")?new Promise(r=>{resolve=r;}):response(path.endsWith("/3")?3:1));
  await sandbox.preview(1);
  const oldLoad=$("preview").onload,oldError=$("preview").onerror;
  oldLoad();
  const pending=sandbox.preview(2);
  oldLoad();oldError();
  assert.ok($("previewWrap").classList.contains("hidden"));
  assert.match($("previewStatus").textContent,/正在加载/);
  await sandbox.preview(3,{box:[0.1,0.2,0.3,0.4],text:"第三页证据"});
  $("preview").onload();
  resolve(response(2));await pending;
  assert.equal($("preview").src,"blob:3");
  assert.equal($("previewPage").value,"3");
  assert.ok(!$("highlight").classList.contains("hidden"));
  assert.match($("evidenceText").textContent,/第 3 页/);
  assert.deepEqual(urls,["blob:1","blob:3"]);
  assert.deepEqual(revoked,["blob:1"]);
});

test("closing a document invalidates its pending image request",async()=>{
  let resolve;
  const {$,sandbox,urls}=setup(()=>new Promise(r=>{resolve=r;}));
  const pending=sandbox.preview(1);
  sandbox.resetPreview();
  resolve(response(1));await pending;
  assert.deepEqual(urls,[]);
  assert.ok($("previewWrap").classList.contains("hidden"));
});

test("unauthorized preview response keeps image hidden and expires the session",async()=>{
  const {$,sandbox,logouts}=setup(async()=>({ok:false,status:401}));
  await sandbox.preview(1);
  assert.deepEqual(logouts,[["student",true]]);
  assert.ok($("previewWrap").classList.contains("hidden"));
});

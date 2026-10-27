import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import vm from "node:vm";
import test from "node:test";

const source=readFileSync(new URL("../src/patient_follow_up_system/web/team.js",import.meta.url),"utf8");
const settle=()=>new Promise(resolve=>setImmediate(resolve));
class Element {
  constructor(){this.children=[];this.value="";this.checked=false;this.type="password";this.attributes={};this.className="hidden";this.open=false;this.dataset={};this.classList={toggle:(name,on)=>{const names=new Set(this.className.split(" ").filter(Boolean));if(on??!names.has(name))names.add(name);else names.delete(name);this.className=[...names].join(" ");},remove:name=>this.classList.toggle(name,false),add:name=>this.classList.toggle(name,true),contains:name=>this.className.split(" ").includes(name)};}
  showModal(){this.open=true;}
  close(){this.open=false;this.onclose?.();}
  focus(){this.focused=true;}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=[...nodes];}
  setAttribute(key,value){this.attributes[key]=value;}
  setCustomValidity(value){this.validity=value;}
  reportValidity(){this.reported=true;}
  querySelector(){return this.submitButton??=new Element();}
}
async function setup(role="doctor"){
  const elements=new Map(),calls=[];
  const $=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  $("studentForm").reset=()=>["studentUsername","studentName","studentPassword","studentConfirm"].forEach(id=>{$(id).value="";});
  $("grantForm").reset=()=>{["grantStudent","grantNote","grantStart","grantEnd"].forEach(id=>{$(id).value="";});$("grantView").checked=true;$("grantPermanent").checked=false;$("grantEdit").checked=false;$("grantReview").checked=false;};
  const responses={"/auth/me":{role,display_name:"虚构医生"},"/doctor/students":[{id:8,username:"fixture",display_name:"虚构学生",is_active:true}],"/doctor/student-permissions":[]};
  const sandbox={document:{getElementById:$,createElement:()=>new Element(),querySelectorAll:()=>[]},AppSession:{staffRole:()=>role,require:()=>"fixture-token",logout(){}},DoctorShell:{setUser(){}},Intl,Date,Option:function(text,value){this.textContent=text;this.value=value;},AppPaths:{fetch:async(path,options={})=>{calls.push({path,...options,body:options.body?JSON.parse(options.body):undefined});return {ok:true,json:async()=>responses[path]??{}};}}};
  vm.createContext(sandbox);vm.runInContext(source,sandbox);await settle();await settle();return {$,calls,responses};
}

test("doctor cannot submit mismatched student passwords and successful creation clears them",async()=>{
  const {$,calls}=await setup();$("newStudent").onclick();$("studentUsername").value="fictional_student";$("studentName").value="虚构学生";$("studentPassword").value="Fixture-123456";$("studentConfirm").value="different";
  await $("studentForm").onsubmit({preventDefault(){},target:$("studentForm")});
  assert.ok($("studentConfirm").reported);assert.ok(!calls.some(c=>c.method==="POST"));
  $("studentConfirm").value="Fixture-123456";await $("showPassword").onclick();
  await $("studentForm").onsubmit({preventDefault(){},target:$("studentForm")});
  const request=calls.find(c=>c.method==="POST");assert.equal(request.path,"/doctor/students");
  assert.deepEqual(request.body,{username:"fictional_student",display_name:"虚构学生",password:"Fixture-123456"});
  assert.equal($("studentPassword").value,"");assert.equal($("studentConfirm").value,"");assert.equal($("studentPassword").type,"password");assert.equal($("showPassword").attributes["aria-pressed"],"false");assert.equal($("studentDialog").open,false);
});

test("student permissions have no patient selector, optional note and timezone-aware period",async()=>{
  const {$,calls}=await setup();await $("students").children[0].children[5].children[0].children[0].onclick();$("grantStudent").value="8";$("grantNote").value="";$("grantEdit").checked=true;$("grantReview").checked=false;
  await $("grantForm").onsubmit({preventDefault(){},target:$("grantForm")});
  const request=calls.find(c=>c.method==="POST");assert.equal(request.path,"/doctor/student-permissions");
  assert.equal(request.body.student_id,8);assert.ok(!Object.hasOwn(request.body,"patient_id"));assert.equal(request.body.can_view,true);assert.equal(request.body.can_edit,true);assert.equal(request.body.can_review,false);assert.equal(request.body.note,"");assert.equal($("grantDialog").open,false);assert.ok(request.body.starts_at.endsWith("Z"));assert.ok(new Date(request.body.ends_at)>new Date(request.body.starts_at));
});

test("student who directly visits team page cannot load doctor controls",async()=>{
  const {$,calls}=await setup("student");assert.deepEqual(calls.map(c=>c.path),["/auth/me"]);assert.equal($("teamContent").className,"hidden");assert.match($("message").textContent,/只有医生/);
});

test("invalid grant date is rejected before a request is sent",async()=>{
  const {$,calls}=await setup();await $("students").children[0].children[5].children[0].children[0].onclick();$("grantEnd").value="2020-01-01";
  await $("grantForm").onsubmit({preventDefault(){},target:$("grantForm")});assert.ok(!calls.some(c=>c.method==="POST"));assert.match($("grantError").textContent,/截止日期/);assert.equal($("grantDialog").open,true);
});


test("page starts with a student list and opens forms only through dialogs",async()=>{
  const {$,calls}=await setup();
  assert.equal($("students").children.length,1);
  for(const id of ["studentDialog","grantDialog"])assert.equal($(id).open,false);
  assert.equal($("message").className,"hidden");
  $("newStudent").onclick();assert.equal($("studentDialog").open,true);assert.ok($("studentUsername").focused);
  $("studentPassword").value="Unsaved-password";$("showPassword").onclick();$("studentDialog").close();
  assert.equal($("studentPassword").value,"");assert.equal($("studentPassword").type,"password");
  const assign=$("students").children[0].children[5].children[0].children[0];await assign.onclick();
  assert.equal($("grantDialog").open,true);assert.equal($("grantStudent").value,"8");assert.equal($("grantDialogTitle").textContent,"虚构学生的权限");
  assert.ok(!calls.some(c=>c.method==="POST"));
});

test("student row offers settings without history and reloads existing configuration",async()=>{
  const {$,responses}=await setup();
  responses["/doctor/student-permissions"]=[
    {id:51,student_id:8,scope:"doctor",can_view:true,can_edit:true,can_review:false,is_permanent:true,state:"active",note:"保留的备注",starts_at:null,ends_at:null},
    {id:52,student_id:99,scope:"doctor",can_view:true,can_review:true,is_permanent:true,state:"active",note:"其他学生配置",starts_at:null,ends_at:null},
  ];
  await $("refreshTeam").onclick();
  const actions=$("students").children[0].children[5].children[0].children;
  assert.deepEqual(actions.map(button=>button.textContent),["设置权限","停用"]);
  await actions[0].onclick();
  assert.equal($("grantDialog").open,true);assert.equal($("grantStudent").value,"8");
  assert.equal($("grantNote").value,"保留的备注");assert.equal($("grantPermanent").checked,true);assert.equal($("grantEdit").checked,true);assert.equal($("grantReview").checked,false);
});


test("permanent permission disables dates and submits null bounds",async()=>{
  const {$,calls}=await setup();await $("students").children[0].children[5].children[0].children[0].onclick();
  assert.equal($("grantView").checked,true);$("grantPermanent").checked=true;$("grantPermanent").onchange();
  assert.equal($("grantPeriod").disabled,true);assert.equal($("grantStart").disabled,true);assert.equal($("grantEnd").disabled,true);assert.equal($("grantStart").required,false);
  $("grantStart").value="";$("grantEnd").value="";
  await $("grantForm").onsubmit({preventDefault(){}});
  const request=calls.find(c=>c.method==="POST");assert.equal(request.body.is_permanent,true);assert.equal(request.body.starts_at,null);assert.equal(request.body.ends_at,null);
});

test("view can be unchecked and then edit/review are cleared and disabled",async()=>{
  const {$,calls}=await setup();await $("students").children[0].children[5].children[0].children[0].onclick();
  $("grantEdit").checked=true;$("grantReview").checked=true;$("grantView").checked=false;$("grantView").onchange();
  for(const id of ["grantEdit","grantReview"]){assert.equal($(id).checked,false);assert.equal($(id).disabled,true);}
  $("grantPermanent").checked=true;$("grantPermanent").onchange();await $("grantForm").onsubmit({preventDefault(){}});
  const request=calls.find(c=>c.method==="POST");assert.equal(request.body.can_view,false);assert.equal(request.body.can_edit,false);assert.equal(request.body.can_review,false);
});

test("same-day date interval includes the entire selected end day",async()=>{
  const {$,calls}=await setup();await $("students").children[0].children[5].children[0].children[0].onclick();
  $("grantStart").value="2030-02-03";$("grantEnd").value="2030-02-03";
  await $("grantForm").onsubmit({preventDefault(){}});
  const request=calls.find(c=>c.method==="POST");assert.equal(request.body.starts_at,new Date("2030-02-03T00:00:00").toISOString());assert.equal(request.body.ends_at,new Date("2030-02-04T00:00:00").toISOString());
});

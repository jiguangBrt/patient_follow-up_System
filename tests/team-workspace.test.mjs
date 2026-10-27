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
  $("grantForm").reset=()=>{["grantStudent","grantPatient","grantPurpose","grantStart","grantEnd"].forEach(id=>{$(id).value="";});$("grantEdit").checked=false;$("grantReview").checked=false;};
  const responses={"/auth/me":{role,display_name:"虚构医生"},"/doctor/students":[{id:8,username:"fixture",display_name:"虚构学生",is_active:true}],"/patients":[{id:9,display_name:"虚构患者",patient_code:"P9"}],"/doctor/patient-grants":[]};
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

test("grant form carries patient scope, purpose, separate operations and timezone-aware times",async()=>{
  const {$,calls}=await setup();await $("students").children[0].children[5].children[0].children[0].onclick();$("grantStudent").value="8";$("grantPatient").value="9";$("grantPurpose").value="虚构病例整理";$("grantEdit").checked=true;$("grantReview").checked=false;
  await $("grantForm").onsubmit({preventDefault(){},target:$("grantForm")});
  const request=calls.find(c=>c.method==="POST");assert.equal(request.path,"/doctor/patient-grants");
  assert.equal(request.body.student_id,8);assert.equal(request.body.patient_id,9);assert.equal(request.body.can_edit,true);assert.equal(request.body.can_review,false);assert.equal(request.body.purpose,"虚构病例整理");assert.equal($("grantDialog").open,false);assert.ok(request.body.starts_at.endsWith("Z"));assert.ok(new Date(request.body.ends_at)>new Date(request.body.starts_at));
});

test("student who directly visits team page cannot load doctor controls",async()=>{
  const {$,calls}=await setup("student");assert.deepEqual(calls.map(c=>c.path),["/auth/me"]);assert.equal($("teamContent").className,"hidden");assert.match($("message").textContent,/只有医生/);
});

test("invalid grant date is rejected before a request is sent",async()=>{
  const {$,calls}=await setup();await $("students").children[0].children[5].children[0].children[0].onclick();$("grantEnd").value="2020-01-01T12:00";
  await $("grantForm").onsubmit({preventDefault(){},target:$("grantForm")});assert.ok(!calls.some(c=>c.method==="POST"));assert.match($("grantError").textContent,/结束时间/);assert.equal($("grantDialog").open,true);
});


test("page starts with a student list and opens forms only through dialogs",async()=>{
  const {$,calls}=await setup();
  assert.equal($("students").children.length,1);
  for(const id of ["studentDialog","grantDialog","recordsDialog"])assert.equal($(id).open,false);
  assert.equal($("message").className,"hidden");
  $("newStudent").onclick();assert.equal($("studentDialog").open,true);assert.ok($("studentUsername").focused);
  $("studentPassword").value="Unsaved-password";$("showPassword").onclick();$("studentDialog").close();
  assert.equal($("studentPassword").value,"");assert.equal($("studentPassword").type,"password");
  const assign=$("students").children[0].children[5].children[0].children[0];await assign.onclick();
  assert.equal($("grantDialog").open,true);assert.equal($("grantStudent").value,"8");assert.match($("grantStudentName").textContent,/虚构学生/);
  assert.ok(!calls.some(c=>c.method==="POST"));
});

test("authorization history is scoped to the selected student and can switch to assignment",async()=>{
  const {$,responses}=await setup();
  responses["/doctor/patient-grants"]=[
    {id:51,student_id:8,patient_id:9,state:"active",purpose:"虚构用途",starts_at:new Date().toISOString(),ends_at:new Date(Date.now()+86400000).toISOString()},
    {id:52,student_id:99,patient_id:9,state:"active",purpose:"另一个学生的记录",starts_at:new Date().toISOString(),ends_at:new Date(Date.now()+86400000).toISOString()},
  ];
  const records=$("students").children[0].children[5].children[0].children[1];await records.onclick();
  assert.equal($("recordsDialog").open,true);assert.equal($("grants").children.length,1);
  $("grantFromRecords").onclick();assert.equal($("recordsDialog").open,false);assert.equal($("grantDialog").open,true);assert.equal($("grantStudent").value,"8");
});

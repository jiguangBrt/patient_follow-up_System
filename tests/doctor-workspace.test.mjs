import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import test from "node:test";

const source=readFileSync(new URL("../src/patient_follow_up_system/web/doctor.js",import.meta.url),"utf8");
class Element {
  constructor(tag="div"){this.tag=tag;this.children=[];this.value="";this.className="";this.dataset={};this.attributes={};this.scrollTop=0;this.open=false;
    this.classList={contains:c=>this.className.split(" ").includes(c),add:c=>{this.classList.toggle(c,true);},remove:c=>{this.classList.toggle(c,false);},toggle:(c,on)=>{const names=new Set(this.className.split(" ").filter(Boolean));const add=on??!names.has(c);if(add)names.add(c);else names.delete(c);this.className=[...names].join(" ");}};
  }
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=[...children];}
  setAttribute(key,value){this.attributes[key]=value;}
  showModal(){this.open=true;}
  close(){this.open=false;this.onclose?.();}
  focus(){}
  click(){return this.onclick?.();}
}
const patients=[{id:1,display_name:"虚构患者甲",patient_code:"P1"},{id:2,display_name:"虚构患者乙",patient_code:"P2"}];
function workspace(label="Fixture") {return {profile:null,unfiled:[],visits:[{date:"2026-08-11",records:[{kind:"clinical",id:8,original_name:label,fields:[{label:"主诉",value:"虚构内容"}]}]}]};}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
async function setup(override={}) {
  const elements=new Map();const $=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  for(const id of ["patientsCard","intakesCard","noticeCard","placeholderCard","inviteCard","newPatientCard","message"])$(id).className="hidden";
  const calls=[];let resolver=override.resolve;
  const storage=new Map();const location={hash:"#patients",href:"https://example.test/patientfollowup/doctor#patients"};
  const sandbox={document:{getElementById:$,createElement:tag=>new Element(tag),createTextNode:text=>({textContent:text}),body:new Element("body")},AppSession:{require:()=>"fixture-token"},AppPaths:{url:p=>"/patientfollowup"+p,storage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},fetch:async(path,options={})=>{
    calls.push(path);let data;
    if(path==="/auth/me")data={id:11,role:"doctor",display_name:"Fixture doctor"};
    else if(path==="/patients")data=patients;
    else if(path==="/doctor/patient-notices/current")data={title:"Fixture notice",version:"1",content:"Fixture"};
    else if(path.endsWith("/intake-link"))data={id:9,display_name:"虚构患者甲",state:"available",intake_url:"https://example.test/patientfollowup/intake#token=fixture",qr_svg:"<svg/>"};
    else if(path.endsWith("/workspace"))data=resolver?await resolver(path):workspace();
    else throw new Error("Unexpected request: "+path);
    return {ok:true,headers:{get:()=>"application/json"},json:async()=>data};
  }},DoctorShell:{activate(){},setUser(){}},window:{addEventListener(){}},location};
  vm.createContext(sandbox);vm.runInContext(source,sandbox);await settle();await settle();
  return {$,calls,sandbox,location,setResolver:r=>{resolver=r;}};
}
function texts(root,tag){return root.children.flatMap(child=>[...(child.tag===tag?[child.textContent]:[]),...texts(child,tag)]);}

test("patient names switch the large workspace without changing URL or expanding rows",async()=>{
  const {$,location}=await setup();const before=location.href;
  assert.equal($("patients").children.length,2);
  assert.equal($("patients").children[0].textContent,"虚构患者甲");
  assert.equal($("patients").children[0].children.length,0);
  await $("patients").children[1].click();
  assert.equal($("patientHeading").textContent,"虚构患者乙");
  assert.equal(location.href,before);assert.equal(location.hash,"#patients");
  assert.ok(texts($("patientDetailScroll"),"h2").includes("2026-08-11 · 就诊记录"));
});

test("QR is fetched and shown only by explicit button, then closes cleanly",async()=>{
  const {$,calls}=await setup();assert.equal($("inviteCard").open,false);assert.ok(!calls.some(p=>p.endsWith("/intake-link")));
  await $("showPatientQr").click();assert.equal($("inviteCard").open,true);assert.equal(calls.filter(p=>p.endsWith("/intake-link")).length,1);
  $("closeInvite").click();assert.equal($("inviteCard").open,false);assert.ok($("inviteCard").classList.contains("hidden"));
});

test("a slower previous patient request cannot overwrite the new selection",async()=>{
  const {$,sandbox,setResolver}=await setup();let resolveSecond;
  setResolver(path=>path.includes("/2/")?new Promise(resolve=>{resolveSecond=resolve;}):workspace("Patient one"));
  const slow=sandbox.selectPatient(2);await settle();await sandbox.selectPatient(1);resolveSecond(workspace("Patient two"));await slow;
  assert.equal($("patientHeading").textContent,"虚构患者甲");
  assert.ok(texts($("patientDetailScroll"),"h3").includes("Patient one"));
  assert.ok(!texts($("patientDetailScroll"),"h3").includes("Patient two"));
});

test("search changes only the name list and keeps the active archive",async()=>{
  const {$}=await setup();$("patientSearch").value="患者乙";$("patientSearch").oninput();
  assert.equal($("patients").children.length,1);assert.equal($("patients").children[0].textContent,"虚构患者乙");
  assert.equal($("patientHeading").textContent,"虚构患者甲");
});

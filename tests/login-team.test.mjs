import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import vm from "node:vm";
import test from "node:test";

const source=readFileSync(new URL("../src/patient_follow_up_system/web/login.js",import.meta.url),"utf8");
class Element {
  constructor(role){this.dataset={role};this.value="";this.attributes={};}
  setAttribute(key,value){this.attributes[key]=value;}
  replaceChildren(...children){this.textContent=children.map(c=>c.textContent).join("");}
  focus(){}
}
function setup(actualRole,entry="team"){
  const elements=new Map(),tabs=["patient","team","admin"].map(role=>new Element(role));
  const $=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  const calls=[],saved=[],destinations=[],historyURLs=[];
  const sandbox={document:{getElementById:$,querySelectorAll:()=>tabs,createTextNode:text=>({textContent:text})},URL,URLSearchParams,
    location:{href:`https://example.test/patientfollowup/?role=${entry}`,search:`?role=${entry}`,replace:url=>destinations.push(url)},history:{replaceState:(_,__,url)=>historyURLs.push(url)},
    AppSession:{roles:{doctor:{path:"/patientfollowup/doctor"},student:{path:"/patientfollowup/doctor"},patient:{path:"/patientfollowup/patient"},admin:{path:"/patientfollowup/admin"}},save:(token,role)=>saved.push({token,role})},
    AppPaths:{fetch:async(path,options)=>{calls.push({path,options});return {ok:true,json:async()=>path==="/auth/login"?{access_token:"fixture-token"}:{role:actualRole}};}}};
  vm.createContext(sandbox);vm.runInContext(source,sandbox);
  return {$,tabs,calls,saved,destinations,historyURLs};
}

for(const role of ["doctor","student"])test(`team entry uses the database's actual ${role} identity`,async()=>{
  const {$,calls,saved,destinations}=setup(role);$("username").value="fixture";$("password").value="Fixture-password";
  await $("loginForm").onsubmit({preventDefault(){}});
  assert.equal(JSON.parse(calls[0].options.body).role,"team");
  assert.deepEqual(saved,[{token:"fixture-token",role}]);assert.deepEqual(destinations,["/patientfollowup/doctor"]);assert.equal($("password").value,"");
});

test("old doctor and student login links select the single team tab",()=>{
  for(const oldRole of ["doctor","student"]){const {$,tabs,historyURLs}=setup(oldRole,oldRole);assert.equal(tabs[1].attributes["aria-selected"],"true");assert.equal($("submitLogin").textContent,"登录医生团队");assert.ok(historyURLs[0].endsWith("?role=team"));}
});

test("team entry never saves a returned non-team identity",async()=>{
  const {$,saved,destinations}=setup("patient");await $("loginForm").onsubmit({preventDefault(){}});assert.equal(saved.length,0);assert.equal(destinations.length,0);assert.match($("loginMessage").textContent,/身份与所选入口不一致/);
});

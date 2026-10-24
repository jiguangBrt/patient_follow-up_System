import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../src/patient_follow_up_system/web/clinical.js", import.meta.url), "utf8");
const helper = source.slice(source.indexOf("function reviewedFields("), source.indexOf("async function review("));
function payload(action) {
  const entries = [
    ["name", { value:{value:" 候选姓名 "}, field:{candidate_value:"候选姓名",candidate_status:"recognized",review_status:"pending"} }],
    ["edited", { value:{value:"医生更正"}, field:{candidate_value:"误识别",candidate_status:"recognized",review_status:"pending"} }],
    ["empty", { value:{value:""}, field:{candidate_value:"已清空候选",candidate_status:"recognized",review_status:"pending"} }],
    ["conflict", { value:{value:"有冲突"}, field:{candidate_value:"有冲突",candidate_status:"conflict",review_status:"pending"} }],
    ["locked", { locked:true, value:{value:"已入档"},field:{} }],
  ];
  const context = vm.createContext({editors:new Map(entries)});
  vm.runInContext(helper, context);
  return JSON.parse(JSON.stringify(context.reviewedFields(action)));
}
test("save preserves edited and cleared values as pending drafts", () => {
  const result=payload("save");
  assert.equal(result.length,4);
  assert.ok(result.every(item=>item.review_status==="pending"));
  assert.equal(result[1].confirmed_value,"医生更正");
  assert.equal(result[2].confirmed_value,"");
});
test("global filing confirms nonempty values and skips blank values", () => {
  assert.deepEqual(payload("file").map(item=>item.review_status),["confirmed","corrected","pending","corrected"]);
});
test("reject does not silently confirm or save current edits", () => {
  assert.deepEqual(payload("reject"),[]);
});

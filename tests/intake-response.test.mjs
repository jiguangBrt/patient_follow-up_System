import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../src/patient_follow_up_system/web/intake.js", import.meta.url), "utf8");
const helpers = source.slice(source.indexOf("async function request("), source.indexOf("// End response helpers."));

function client(status, body) {
  const context = vm.createContext({ AppPaths: { fetch: async () => new Response(body, { status }) } });
  vm.runInContext("let accessToken = null;\n" + helpers, context);
  return () => context.request("/intake-submissions", {});
}

test("HTML proxy failures produce readable messages and preserve HTTP status", async () => {
  for (const status of [500, 502, 504]) {
    await assert.rejects(client(status, "<html><h1>Server Error</h1></html>"), error =>
      error.status === status && error.message.includes("服务器暂时无法接收请求"));
  }
  await assert.rejects(client(413, "<html>Request Entity Too Large</html>"), error =>
    error.status === 413 && error.message.includes("8 MB"));
});

test("JSON success and application errors retain their original behavior", async () => {
  assert.equal((await client(201, '{"id":7,"status":"pending"}')()).id, 7);
  await assert.rejects(client(409, '{"detail":"信息已提交，等待医生审核"}'), error =>
    error.status === 409 && error.message === "信息已提交，等待医生审核");
  await assert.rejects(client(422, '{"detail":[{"msg":"Invalid input"}]}'), /请检查填写的信息和文件/);
});

test("unexpected HTML success is reported without leaking a JSON parser error", async () => {
  await assert.rejects(client(200, "<html>Unexpected page</html>"), /服务器返回了异常内容/);
});

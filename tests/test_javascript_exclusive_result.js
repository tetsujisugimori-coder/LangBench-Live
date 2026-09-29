const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { test } = require("node:test");
const { writeResult } = require("../benchmarks/function_call_numeric_sum/javascript/main.js");

test("exclusive result writing preserves an existing diagnostic raw", (t) => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "langbench-exclusive-"));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const resultPath = path.join(directory, "diagnostics", "javascript.json");
  fs.mkdirSync(path.dirname(resultPath));
  const original = "existing diagnostic raw\n";
  fs.writeFileSync(resultPath, original);

  assert.throws(() => writeResult(resultPath, { replacement: true }, true), { code: "EEXIST" });
  assert.equal(fs.readFileSync(resultPath, "utf8"), original);
});

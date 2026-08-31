const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {
  optimizationAnalysis,
  parseManifestEntry,
} = require("../benchmarks/function_call_numeric_sum/javascript/main.js");

function fixture() {
  const condition = {
    source_sha256: "a".repeat(64),
    implementation: { name: "V8", version: "13.6.0" },
    architecture: "x64",
    options: [],
  };
  return {
    condition,
    entry: {
      artifact_id: "test-javascript",
      analyzed_at: "2026-08-31T12:00:00Z",
      applies_to: ["jit", "inlining", "vectorization", "simd"],
      condition: structuredClone(condition),
      generation_commands: ["node", "--trace-opt", "main.js"],
      findings: {
        jit: { result: "detected" },
        inlining: { result: "detected" },
        vectorization: { result: "not_checked" },
        simd: { result: "not_checked", isa: [] },
      },
      evidence: [{ type: "jit_trace", path: "artifacts/function-call-analysis/v8-optimization.txt" }],
    },
  };
}

test("malformed JSON and a missing language entry are unavailable", () => {
  const { condition } = fixture();
  for (const content of ["{", '{"languages":{}}']) {
    const analysis = optimizationAnalysis(parseManifestEntry(content), condition);
    assert.equal(analysis.provenance.status, "unavailable");
    assert.deepEqual(analysis.provenance.mismatches, ["manifest_invalid"]);
  }
});

test("the complete manifest is validated before JavaScript findings are used", async t => {
  const manifestPath = path.join(__dirname, "..", "artifacts", "function-call-analysis", "manifest.json");
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  const current = structuredClone(manifest.languages.javascript.condition);
  const valid = optimizationAnalysis(parseManifestEntry(JSON.stringify(manifest)), current);
  assert.equal(valid.provenance.status, "matched");

  const cases = [
    ["schema version", document => { document.schema_version = "2.0"; }],
    ["analysis id missing", document => { delete document.analysis_id; }],
    ["generated at invalid", document => { document.generated_at = "not-a-timestamp"; }],
    ["languages array", document => { document.languages = []; }],
    ["languages null", document => { document.languages = null; }],
    ["sibling missing", document => { delete document.languages.python; }],
    ["unknown root field", document => { document.unexpected = true; }],
  ];
  for (const [name, mutate] of cases) {
    await t.test(name, () => {
      const candidate = structuredClone(manifest);
      mutate(candidate);
      const analysis = optimizationAnalysis(parseManifestEntry(JSON.stringify(candidate)), structuredClone(current));
      assert.equal(analysis.provenance.status, "unavailable");
      assert.equal(analysis.provenance.matched, false);
      assert.deepEqual(analysis.provenance.mismatches, ["manifest_invalid"]);
      for (const field of ["artifact_id", "analyzed_at", "analysis", "artifact_findings"]) {
        assert.equal(analysis.provenance[field], null);
      }
      assert.equal(analysis.jit.result, "unknown");
      assert.equal(analysis.inlining.result, "unknown");
      assert.equal(analysis.vectorization.result, "unknown");
      assert.deepEqual(analysis.simd, { result: "unknown", isa: [] });
      assert.deepEqual(analysis.evidence, []);
    });
  }
});

test("matching provenance applies saved V8 findings", () => {
  const { condition, entry } = fixture();
  const analysis = optimizationAnalysis(entry, condition);
  assert.equal(analysis.provenance.status, "matched");
  assert.equal(analysis.jit.result, "detected");
  assert.equal(analysis.inlining.result, "detected");
});

for (const [name, mutate] of [
  ["source hash", current => current.source_sha256 = "b".repeat(64)],
  ["V8 version", current => current.implementation.version = "13.7.0"],
  ["architecture", current => current.architecture = "arm64"],
  ["jitless option", current => current.options = ["--jitless"]],
]) {
  test(`${name} mismatch does not reuse JIT findings`, () => {
    const { condition, entry } = fixture();
    const current = structuredClone(condition);
    mutate(current);
    const analysis = optimizationAnalysis(entry, current);
    assert.equal(analysis.provenance.status, "mismatched");
    assert.equal(analysis.jit.result, "not_checked");
    assert.equal(analysis.inlining.result, "not_checked");
    assert.deepEqual(analysis.simd.isa, []);
  });
}

test("matching provenance uses manifest findings instead of fixed values", () => {
  const { condition, entry } = fixture();
  entry.findings.jit.result = "not_checked";
  entry.findings.inlining.result = "unknown";
  const analysis = optimizationAnalysis(entry, condition);
  assert.equal(analysis.jit.result, "not_checked");
  assert.equal(analysis.inlining.result, "unknown");
  assert.deepEqual(analysis.provenance.artifact_findings, entry.findings);
});

for (const [name, mutate] of [
  ["null entry", () => null],
  ["missing condition", entry => { delete entry.condition; return entry; }],
  ["missing findings", entry => { delete entry.findings; return entry; }],
  ["invalid implementation", entry => { entry.condition.implementation = "V8"; return entry; }],
  ["invalid evidence", entry => { entry.evidence = "trace.txt"; return entry; }],
]) {
  test(`${name} is unavailable without throwing`, () => {
    const { condition, entry } = fixture();
    const analysis = optimizationAnalysis(mutate(entry), condition);
    assert.equal(analysis.provenance.status, "unavailable");
    assert.equal(analysis.provenance.artifact_findings, null);
    assert.equal(analysis.jit.result, "unknown");
    assert.equal(analysis.inlining.result, "unknown");
  });
}

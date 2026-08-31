const test = require("node:test");
const assert = require("node:assert/strict");
const {
  optimizationAnalysis,
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
      evidence: [{ type: "jit_trace", path: "artifacts/function-call-analysis/v8-optimization.txt" }],
    },
  };
}

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

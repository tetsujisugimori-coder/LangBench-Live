const fs = require("fs");
const os = require("os");
const path = require("path");

const PROJECT = "LangBench Live";
const SCHEMA_VERSION = "1.0";
const LANGUAGE = "javascript";
const BENCHMARK = "jit_object_numeric_sum";
const ARRAY_SIZE = 1_000_000;
const ITERATIONS = 50;
const WARMUP_ITERATIONS = 5;
const RESULT_FILE = "jit_object_numeric_sum_javascript_result.json";
const RUNNER = "vscode_terminal_powershell";
const RUNNER_LABEL = "VSCode Terminal / PowerShell";
const EXPECTED_CHECKSUM = 500_000_500_000;

function getProjectRoot() {
  return path.resolve(__dirname, "..", "..", "..");
}

function nowNs() {
  return process.hrtime.bigint();
}

function elapsedMs(startNs, endNs) {
  return roundMs(Number(endNs - startNs) / 1_000_000);
}

function roundMs(value) {
  return Math.round(value * 1000) / 1000;
}

function parseArg(name) {
  const match = process.argv.find((arg) => arg.startsWith(`${name}=`));
  return match ? match.split("=", 2)[1] : null;
}

function getExperimentId() {
  return (
    parseArg("--experiment-id") ||
    process.env.LANGBENCH_EXPERIMENT_ID ||
    generateExperimentId()
  );
}

function getRunId() {
  return (
    parseArg("--run-id") ||
    process.env.LANGBENCH_RUN_ID ||
    generateRunId()
  );
}

function generateExperimentId() {
  const now = new Date();
  return `${formatDate(now)}_${BENCHMARK}`;
}

function generateRunId() {
  const now = new Date();
  return `${formatDate(now)}_${LANGUAGE}_${BENCHMARK}`;
}

function formatDate(date) {
  const z = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}${z(date.getMonth() + 1)}${z(date.getDate())}_${z(
    date.getHours()
  )}${z(date.getMinutes())}${z(date.getSeconds())}`;
}

function createObjectArray(arraySize) {
  const values = new Array(arraySize);

  for (let index = 0; index < arraySize; index += 1) {
    values[index] = { value: index + 1 };
  }

  return values;
}

function sumObjectValues(values) {
  let total = 0;

  for (let index = 0; index < values.length; index += 1) {
    total += values[index].value;
  }

  return total;
}

function summarizeSamples(samplesMs) {
  const sortedElapsedValues = [...samplesMs].sort((a, b) => a - b);
  const totalMs = samplesMs.reduce((sum, value) => sum + value, 0);
  const middleIndex = Math.floor(sortedElapsedValues.length / 2);
  const medianMs = sortedElapsedValues.length % 2 === 0
    ? (sortedElapsedValues[middleIndex - 1] + sortedElapsedValues[middleIndex]) / 2
    : sortedElapsedValues[middleIndex];

  return {
    samples_ms: samplesMs,
    min_ms: roundMs(Math.min(...samplesMs)),
    max_ms: roundMs(Math.max(...samplesMs)),
    mean_ms: roundMs(totalMs / samplesMs.length),
    median_ms: roundMs(medianMs),
  };
}

function buildMetadata(projectRoot, status, experimentId, runId) {
  const cpus = os.cpus();
  const osPlatform = os.platform();

  return {
    type: "langbench_result",
    schema_version: SCHEMA_VERSION,
    project: PROJECT,
    benchmark: BENCHMARK,
    experiment_id: experimentId,
    run_id: runId,
    language: LANGUAGE,
    created_at: getLocalIsoTimestamp(),
    status,
    engine: {
      runtime: "node",
      runtime_version: process.version,
      compiler: null,
      compiler_version: null,
      v8_version: process.versions.v8,
    },
    execution: {
      runner: RUNNER,
      runner_label: RUNNER_LABEL,
      cwd: process.cwd(),
      argv: process.argv,
    },
    environment: {
      os: getOsName(osPlatform),
      os_version: os.release(),
      architecture: os.arch() || null,
      cpu: cpus.length > 0 ? cpus[0].model : null,
      logical_processors: cpus.length > 0 ? cpus.length : null,
      memory_bytes: os.totalmem() || null,
    },
  };
}

function getOsName(osPlatform) {
  const osNames = {
    win32: "Windows",
    darwin: "macOS",
    linux: "Linux",
  };
  return osNames[osPlatform] || osPlatform;
}

function getLocalIsoTimestamp() {
  const date = new Date();
  const timezoneOffsetMinutes = -date.getTimezoneOffset();
  const offsetSign = timezoneOffsetMinutes >= 0 ? "+" : "-";
  const absoluteOffsetMinutes = Math.abs(timezoneOffsetMinutes);
  const offsetHours = String(Math.floor(absoluteOffsetMinutes / 60)).padStart(2, "0");
  const offsetMinutes = String(absoluteOffsetMinutes % 60).padStart(2, "0");
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return `${localDate.toISOString().slice(0, 19)}${offsetSign}${offsetHours}:${offsetMinutes}`;
}

function saveResult(result, outputPath) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");
}

function buildConfig() {
  return {
    item_count: ARRAY_SIZE,
    warmup_iterations: WARMUP_ITERATIONS,
    measurement_iterations: ITERATIONS,
    numeric_type: "integer",
    value_field: "value",
  };
}

function emptyTiming() {
  return {
    process_startup_ms: null,
    setup_ms: null,
    warmup_ms: null,
    measurement_ms: null,
    benchmark_total_ms: null,
  };
}

function emptyResults() {
  return {
    samples_ms: [],
    min_ms: null,
    max_ms: null,
    mean_ms: null,
    median_ms: null,
  };
}

function runBenchmark(projectRoot, experimentId, runId) {
  const setupStartNs = nowNs();
  const values = createObjectArray(ARRAY_SIZE);
  const setupMs = elapsedMs(setupStartNs, nowNs());

  const warmupStartNs = nowNs();
  for (let warmup = 0; warmup < WARMUP_ITERATIONS; warmup += 1) {
    const warmupChecksum = sumObjectValues(values);
    if (warmupChecksum !== EXPECTED_CHECKSUM) {
      throw new Error(`warmup checksum mismatch: ${warmupChecksum}`);
    }
  }
  const warmupMs = elapsedMs(warmupStartNs, nowNs());

  const samplesMs = [];
  let checksum = null;
  for (let iteration = 0; iteration < ITERATIONS; iteration += 1) {
    const iterationStartNs = nowNs();
    checksum = sumObjectValues(values);
    const iterationElapsedMs = elapsedMs(iterationStartNs, nowNs());
    if (checksum !== EXPECTED_CHECKSUM) {
      throw new Error(`checksum mismatch: ${checksum}`);
    }
    samplesMs.push(iterationElapsedMs);
  }

  const measurementMs = roundMs(samplesMs.reduce((sum, value) => sum + value, 0));
  const benchmarkTotalMs = roundMs(setupMs + warmupMs + measurementMs);

  return {
    ...buildMetadata(projectRoot, "success", experimentId, runId),
    config: buildConfig(),
    timing: {
      process_startup_ms: null,
      setup_ms: setupMs,
      warmup_ms: warmupMs,
      measurement_ms: measurementMs,
      benchmark_total_ms: benchmarkTotalMs,
    },
    results: summarizeSamples(samplesMs),
    validation: {
      checksum,
      expected_checksum: EXPECTED_CHECKSUM,
      tolerance: 0,
      passed: checksum === EXPECTED_CHECKSUM,
    },
    error: null,
  };
}

function buildErrorResult(projectRoot, status, message, errorType, experimentId, runId) {
  return {
    ...buildMetadata(projectRoot, status, experimentId, runId),
    config: buildConfig(),
    timing: emptyTiming(),
    results: emptyResults(),
    validation: {
      checksum: null,
      expected_checksum: EXPECTED_CHECKSUM,
      tolerance: 0,
      passed: false,
    },
    error: { type: errorType, message },
  };
}

function main() {
  const projectRoot = getProjectRoot();
  const experimentId = getExperimentId();
  const runId = getRunId();

  try {
    const result = runBenchmark(projectRoot, experimentId, runId);
    const outputPath = path.join(projectRoot, "results", RESULT_FILE);

    saveResult(result, outputPath);
    console.log(`status=${result.status}`);
    return result.status === "success" ? 0 : 1;
  } catch (error) {
    const errorResult = buildErrorResult(
      projectRoot,
      "error",
      error.message,
      error.name,
      experimentId,
      runId,
    );
    try {
      saveResult(errorResult, path.join(projectRoot, "results", RESULT_FILE));
    } catch (saveError) {
      console.error("status=error");
      console.error(`message=${saveError.message}`);
    }
    console.error("status=error");
    console.error(`message=${error.message}`);
    return 1;
  }
}

process.exitCode = main();

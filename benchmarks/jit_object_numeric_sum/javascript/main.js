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
  const ms = String(now.getMilliseconds()).padStart(3, "0");
  return `${formatDate(now)}_${ms}_${LANGUAGE}_${BENCHMARK}`;
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

function summarizeResults(results) {
  const elapsedValues = results.map((result) => result.elapsed_ms);
  const sortedElapsedValues = [...elapsedValues].sort((a, b) => a - b);
  const totalMs = elapsedValues.reduce((sum, value) => sum + value, 0);
  const middleIndex = Math.floor(sortedElapsedValues.length / 2);
  const medianMs = sortedElapsedValues.length % 2 === 0
    ? (sortedElapsedValues[middleIndex - 1] + sortedElapsedValues[middleIndex]) / 2
    : sortedElapsedValues[middleIndex];

  return {
    count: results.length,
    average_ms: roundMs(totalMs / results.length),
    median_ms: roundMs(medianMs),
    fastest_ms: roundMs(Math.min(...elapsedValues)),
    slowest_ms: roundMs(Math.max(...elapsedValues)),
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
    experiment: BENCHMARK,
    experiment_id: experimentId,
    run_id: runId,
    language: LANGUAGE,
    created_at: getLocalIsoTimestamp(),
    status,
    engine: {
      runtime: "node",
      node_version: process.version,
      v8_version: process.versions.v8,
    },
    execution: {
      runner: RUNNER,
      runner_label: RUNNER_LABEL,
      cwd: process.cwd(),
      argv: process.argv,
      command: process.argv.map(quoteCommandPart).join(" "),
      script_path: __filename,
    },
    runtime: {
      name: "node",
      version: process.version,
    },
    environment: {
      os_name: getOsName(osPlatform),
      os_platform: osPlatform,
      os_version: os.release(),
      cpu_model: cpus.length > 0 ? cpus[0].model : null,
      cpu_threads: cpus.length > 0 ? cpus.length : null,
      memory_total_bytes: os.totalmem(),
    },
    output_file: path.join(projectRoot, "results", RESULT_FILE),
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

function quoteCommandPart(value) {
  return /\s/.test(value) ? `"${value.replace(/"/g, '\\"')}"` : value;
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

function getStatus(results) {
  return results.every((result) => result.checksum === EXPECTED_CHECKSUM) ? "success" : "failed";
}

function runBenchmark(projectRoot, experimentId, runId) {
  const setupStartNs = nowNs();
  const values = createObjectArray(ARRAY_SIZE);
  const setupMs = elapsedMs(setupStartNs, nowNs());

  const warmupStartNs = nowNs();
  for (let warmup = 0; warmup < WARMUP_ITERATIONS; warmup += 1) {
    const checksum = sumObjectValues(values);
    if (checksum !== EXPECTED_CHECKSUM) {
      throw new Error(`warmup checksum mismatch: ${checksum}`);
    }
  }
  const warmupMs = elapsedMs(warmupStartNs, nowNs());

  const results = [];
  for (let iteration = 1; iteration <= ITERATIONS; iteration += 1) {
    const iterationStartNs = nowNs();
    const checksum = sumObjectValues(values);
    const iterationElapsedMs = elapsedMs(iterationStartNs, nowNs());
    if (checksum !== EXPECTED_CHECKSUM) {
      throw new Error(`checksum mismatch: ${checksum}`);
    }
    results.push({ iteration, elapsed_ms: iterationElapsedMs, checksum });
  }

  const status = getStatus(results);
  const benchmarkTotalMs = roundMs(results.reduce((sum, item) => sum + item.elapsed_ms, 0));
  const postprocessStartNs = nowNs();
  const summary = summarizeResults(results);
  const postprocessMs = elapsedMs(postprocessStartNs, nowNs());

  return {
    ...buildMetadata(projectRoot, status, experimentId, runId),
    array_size: ARRAY_SIZE,
    iterations: ITERATIONS,
    warmup_iterations: WARMUP_ITERATIONS,
    setup_ms: setupMs,
    warmup_ms: warmupMs,
    expected_checksum: EXPECTED_CHECKSUM,
    results,
    summary,
    timing: {
      process_startup_ms: null,
      setup_ms: setupMs,
      warmup_ms: warmupMs,
      compile_ms: null,
      benchmark_total_ms: benchmarkTotalMs,
      postprocess_ms: postprocessMs,
      result_write_ms: null,
      runtime_total_ms: null,
      end_to_end_total_ms: null,
    },
  };
}

function buildErrorResult(projectRoot, status, message, errorType, experimentId, runId) {
  return {
    ...buildMetadata(projectRoot, status, experimentId, runId),
    error_message: message,
    error_type: errorType,
  };
}

function main() {
  const projectRoot = getProjectRoot();
  const experimentId = getExperimentId();
  const runId = getRunId();

  try {
    const result = runBenchmark(projectRoot, experimentId, runId);
    const outputPath = path.join(projectRoot, "results", RESULT_FILE);

    const resultWriteStartNs = nowNs();
    saveResult(result, outputPath);
    const resultWriteMs = elapsedMs(resultWriteStartNs, nowNs());
    result.timing.result_write_ms = resultWriteMs;
    result.timing.runtime_total_ms = roundMs(
      result.timing.setup_ms +
        result.timing.warmup_ms +
        result.timing.benchmark_total_ms +
        result.timing.postprocess_ms +
        result.timing.result_write_ms
    );

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

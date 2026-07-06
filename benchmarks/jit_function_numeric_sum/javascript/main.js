const fs = require("fs");
const os = require("os");
const path = require("path");

const PROJECT = "LangBench Live";
const SCHEMA_VERSION = "1.0";
const LANGUAGE = "javascript";
const BENCHMARK = "jit_function_numeric_sum";
const ARRAY_SIZE = 1000000; // 100万件
const ITERATIONS = 50;
const RESULT_FILE = "jit_function_javascript_result.json";
const RUNNER = "vscode_terminal_powershell";
const RUNNER_LABEL = "VSCode Terminal / PowerShell";
const EXPECTED_CHECKSUM = 1000000000000;

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

function createNumberArray(arraySize) {
  const values = new Array(arraySize);

  for (let index = 0; index < arraySize; index += 1) {
    values[index] = index;
  }

  return values;
}

function transformValue(value) {
  return value * 2 + 1;
}

function sumTransformedArray(values) {
  let total = 0;

  for (let index = 0; index < values.length; index += 1) {
    total += transformValue(values[index]);
  }

  return total;
}

function summarizeResults(results) {
  const elapsedValues = results.map((result) => result.elapsed_ms);
  const sortedElapsedValues = [...elapsedValues].sort((a, b) => a - b);
  const totalMs = elapsedValues.reduce((sum, value) => sum + value, 0);
  const middleIndex = Math.floor(sortedElapsedValues.length / 2);

  return {
    count: results.length,
    average_ms: roundMs(totalMs / results.length),
    median_ms: roundMs(sortedElapsedValues[middleIndex]),
    fastest_ms: roundMs(Math.min(...elapsedValues)),
    slowest_ms: roundMs(Math.max(...elapsedValues)),
  };
}

function buildMetadata(projectRoot) {
  const cpus = os.cpus();
  const osPlatform = os.platform();

  return {
    type: "langbench_result",
    schema_version: SCHEMA_VERSION,
    project: PROJECT,
    benchmark: BENCHMARK,
    experiment: BENCHMARK,
    language: LANGUAGE,
    created_at: getLocalIsoTimestamp(),
    status: "success",
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

function runBenchmark(projectRoot) {
  const setupStartNs = nowNs();
  const values = createNumberArray(ARRAY_SIZE);
  const setupMs = elapsedMs(setupStartNs, nowNs());
  const results = [];

  for (let iteration = 1; iteration <= ITERATIONS; iteration += 1) {
    const startNs = nowNs();
    const checksum = sumTransformedArray(values);
    const iterationElapsedMs = elapsedMs(startNs, nowNs());

    results.push({
      iteration,
      elapsed_ms: iterationElapsedMs,
      checksum,
    });
  }

  return {
    ...buildMetadata(projectRoot),
    array_size: ARRAY_SIZE,
    iterations: ITERATIONS,
    setup_ms: setupMs,
    expected_checksum: EXPECTED_CHECKSUM,
    results,
    summary: summarizeResults(results),
  };
}

function main() {
  try {
    const projectRoot = getProjectRoot();
    const result = runBenchmark(projectRoot);
    saveResult(result, path.join(projectRoot, "results", RESULT_FILE));
  } catch (error) {
    console.error("status=error");
    console.error(`message=${error.message}`);
    return 1;
  }

  console.log("status=success");
  return 0;
}

process.exitCode = main();

const fs = require("fs");
const path = require("path");
const readline = require("readline");

const BENCHMARK = "csv_line_count";
const LANGUAGE = "javascript";
const MEASURE_RUNS = 3;
const SAMPLES = [
  { name: "small", file: "data/readingTest_small.csv", expected_data_rows: 1000 },
  { name: "medium", file: "data/readingTest_medium.csv", expected_data_rows: 100000 },
  { name: "large", file: "data/readingTest_large.csv", expected_data_rows: 1000000 },
];

function getProjectRoot() {
  return path.resolve(__dirname, "..", "..", "..");
}

async function countCsvLines(csvPath) {
  let lineCount = 0;
  const stream = fs.createReadStream(csvPath, { encoding: "utf8" });
  const reader = readline.createInterface({
    input: stream,
    crlfDelay: Infinity,
  });

  for await (const _line of reader) {
    lineCount += 1;
  }

  return lineCount;
}

async function measureOnce(csvPath, runNumber) {
  const startTime = process.hrtime.bigint();
  const lineCount = await countCsvLines(csvPath);
  const elapsedMs = Number(process.hrtime.bigint() - startTime) / 1_000_000;
  return {
    run: runNumber,
    elapsed_ms: roundMs(elapsedMs),
    line_count: lineCount,
  };
}

function summarizeRuns(runs) {
  const elapsedValues = runs.map((run) => run.elapsed_ms);
  const sortedElapsedValues = [...elapsedValues].sort((a, b) => a - b);
  const middleIndex = Math.floor(sortedElapsedValues.length / 2);
  const totalMs = elapsedValues.reduce((sum, value) => sum + value, 0);

  return {
    count: runs.length,
    average_ms: roundMs(totalMs / runs.length),
    median_ms: roundMs(sortedElapsedValues[middleIndex]),
    fastest_ms: roundMs(Math.min(...elapsedValues)),
    slowest_ms: roundMs(Math.max(...elapsedValues)),
  };
}

function roundMs(value) {
  return Math.round(value * 1000) / 1000;
}

function validateSamples(projectRoot) {
  const missingFiles = SAMPLES
    .map((sample) => sample.file)
    .filter((file) => !fs.existsSync(path.join(projectRoot, file)));

  if (missingFiles.length > 0) {
    throw new Error(
      `Missing CSV file(s): ${missingFiles.join(", ")}. Run \`python tools/create_sample_csv.py\` first.`
    );
  }
}

function printSampleResult(sampleResult) {
  console.log(`sample=${sampleResult.sample}`);
  console.log(`file=${sampleResult.file}`);
  console.log(`expected_data_rows=${sampleResult.expected_data_rows}`);
  for (const run of sampleResult.runs) {
    console.log(
      `run=${run.run} elapsed_ms=${run.elapsed_ms.toFixed(3)} line_count=${run.line_count}`
    );
  }

  const summary = sampleResult.summary;
  console.log(
    `summary count=${summary.count} ` +
      `average_ms=${summary.average_ms.toFixed(3)} ` +
      `median_ms=${summary.median_ms.toFixed(3)} ` +
      `fastest_ms=${summary.fastest_ms.toFixed(3)} ` +
      `slowest_ms=${summary.slowest_ms.toFixed(3)}`
  );
}

async function runBenchmark(projectRoot) {
  const samples = [];

  for (const sample of SAMPLES) {
    const csvPath = path.join(projectRoot, sample.file);
    const runs = [];

    for (let runNumber = 1; runNumber <= MEASURE_RUNS; runNumber += 1) {
      runs.push(await measureOnce(csvPath, runNumber));
    }

    const sampleResult = {
      sample: sample.name,
      file: sample.file,
      expected_data_rows: sample.expected_data_rows,
      runs,
      summary: summarizeRuns(runs),
    };
    samples.push(sampleResult);
    printSampleResult(sampleResult);
  }

  return {
    benchmark: BENCHMARK,
    language: LANGUAGE,
    samples,
  };
}

function saveResult(result, outputPath) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");
}

async function main() {
  try {
    const projectRoot = getProjectRoot();
    validateSamples(projectRoot);
    const result = await runBenchmark(projectRoot);
    saveResult(result, path.join(projectRoot, "results", "results", "javascript_result.json"));
  } catch (error) {
    console.error("status=error");
    console.error(`message=${error.message}`);
    return 1;
  }

  console.log("status=success");
  return 0;
}

main().then((exitCode) => {
  process.exitCode = exitCode;
});

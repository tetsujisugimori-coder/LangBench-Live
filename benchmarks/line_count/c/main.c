#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#if defined(_WIN32)
#include <windows.h>
#endif

#define PROJECT "LangBench Live"
#define EXPERIMENT "csv_line_count"
#define EXPERIMENT_LABEL "CSV行数カウント"
#define LANGUAGE "c"
#define SCHEMA_VERSION "1.0"
#define RESULT_FILE "results/c_result.json"
#define RUNNER "vscode_terminal_powershell"
#define RUNNER_LABEL "VSCode Terminal / PowerShell"
#define MEASURE_RUNS 3
#define SAMPLE_COUNT 3
#define LINE_BUFFER_SIZE 8192

typedef struct {
    const char *name;
    const char *file;
    long expected_data_rows;
} Sample;

typedef struct {
    int run;
    long line_count;
    double elapsed_ms;
} RunResult;

typedef struct {
    int count;
    double average_ms;
    double median_ms;
    double fastest_ms;
    double slowest_ms;
} Summary;

typedef struct {
    Sample sample;
    long input_file_size_bytes;
    RunResult runs[MEASURE_RUNS];
    Summary summary;
} SampleResult;

static const Sample SAMPLES[SAMPLE_COUNT] = {
    {"small", "data/readingTest_small.csv", 1000},
    {"medium", "data/readingTest_medium.csv", 100000},
    {"large", "data/readingTest_large.csv", 1000000},
};

static const char *runtime_standard(void) {
#if defined(__STDC_VERSION__) && __STDC_VERSION__ >= 201710L
    return "C17";
#elif defined(__STDC_VERSION__) && __STDC_VERSION__ >= 201112L
    return "C11";
#elif defined(__STDC_VERSION__) && __STDC_VERSION__ >= 199901L
    return "C99";
#else
    return "C90";
#endif
}

static const char *os_name(void) {
#if defined(_WIN32)
    return "Windows";
#elif defined(__APPLE__)
    return "macOS";
#elif defined(__linux__)
    return "Linux";
#else
    return "Other";
#endif
}

static const char *os_platform(void) {
#if defined(_WIN32)
    return "win32";
#elif defined(__APPLE__)
    return "darwin";
#elif defined(__linux__)
    return "linux";
#else
    return "other";
#endif
}

static double round_ms(double value) {
    return ((long long)(value * 1000.0 + 0.5)) / 1000.0;
}

static double current_time_ms(void) {
#if defined(_WIN32)
    LARGE_INTEGER frequency;
    LARGE_INTEGER counter;

    QueryPerformanceFrequency(&frequency);
    QueryPerformanceCounter(&counter);
    return ((double)counter.QuadPart * 1000.0) / (double)frequency.QuadPart;
#else
    return ((double)clock() * 1000.0) / CLOCKS_PER_SEC;
#endif
}

static void build_timestamp(char *buffer, size_t buffer_size) {
    time_t now = time(NULL);
    struct tm *local = localtime(&now);

    if (local == NULL) {
        snprintf(buffer, buffer_size, "1970-01-01T00:00:00");
        return;
    }

    strftime(buffer, buffer_size, "%Y-%m-%dT%H:%M:%S", local);
}

static void write_json_string(FILE *output, const char *value) {
    const unsigned char *cursor = (const unsigned char *)value;

    fputc('"', output);
    while (*cursor != '\0') {
        if (*cursor == '"' || *cursor == '\\') {
            fputc('\\', output);
            fputc(*cursor, output);
        } else if (*cursor == '\n') {
            fputs("\\n", output);
        } else if (*cursor == '\r') {
            fputs("\\r", output);
        } else if (*cursor == '\t') {
            fputs("\\t", output);
        } else {
            fputc(*cursor, output);
        }
        cursor += 1;
    }
    fputc('"', output);
}

static long get_file_size(const char *path) {
    FILE *file = fopen(path, "rb");
    long size;

    if (file == NULL) {
        return -1;
    }

    if (fseek(file, 0, SEEK_END) != 0) {
        fclose(file);
        return -1;
    }

    size = ftell(file);
    fclose(file);
    return size;
}

static long count_csv_lines(const char *path) {
    FILE *file = fopen(path, "r");
    char buffer[LINE_BUFFER_SIZE];
    long line_count = 0;

    if (file == NULL) {
        fprintf(stderr, "status=error\n");
        fprintf(stderr, "message=failed to open CSV file: %s (%s)\n", path, strerror(errno));
        exit(1);
    }

    while (fgets(buffer, sizeof(buffer), file) != NULL) {
        line_count += 1;
    }

    if (ferror(file)) {
        fprintf(stderr, "status=error\n");
        fprintf(stderr, "message=failed to read CSV file: %s\n", path);
        fclose(file);
        exit(1);
    }

    fclose(file);
    return line_count;
}

static RunResult measure_once(const char *path, int run_number) {
    double start_time_ms;
    double end_time_ms;
    RunResult result;

    start_time_ms = current_time_ms();
    result.line_count = count_csv_lines(path);
    end_time_ms = current_time_ms();

    result.run = run_number;
    result.elapsed_ms = round_ms(end_time_ms - start_time_ms);
    return result;
}

static int compare_double(const void *left, const void *right) {
    double a = *(const double *)left;
    double b = *(const double *)right;

    if (a < b) {
        return -1;
    }
    if (a > b) {
        return 1;
    }
    return 0;
}

static Summary summarize_runs(const RunResult runs[MEASURE_RUNS]) {
    Summary summary;
    double elapsed_values[MEASURE_RUNS];
    double total = 0.0;
    int i;

    for (i = 0; i < MEASURE_RUNS; i += 1) {
        elapsed_values[i] = runs[i].elapsed_ms;
        total += runs[i].elapsed_ms;
    }

    qsort(elapsed_values, MEASURE_RUNS, sizeof(double), compare_double);

    summary.count = MEASURE_RUNS;
    summary.average_ms = round_ms(total / MEASURE_RUNS);
    summary.median_ms = round_ms(elapsed_values[MEASURE_RUNS / 2]);
    summary.fastest_ms = round_ms(elapsed_values[0]);
    summary.slowest_ms = round_ms(elapsed_values[MEASURE_RUNS - 1]);

    return summary;
}

static void print_sample_result(const SampleResult *sample_result) {
    int i;

    printf("sample=%s\n", sample_result->sample.name);
    printf("input=%s\n", sample_result->sample.file);
    printf("expected_data_rows=%ld\n", sample_result->sample.expected_data_rows);

    for (i = 0; i < MEASURE_RUNS; i += 1) {
        printf(
            "run=%d elapsed_ms=%.3f line_count=%ld\n",
            sample_result->runs[i].run,
            sample_result->runs[i].elapsed_ms,
            sample_result->runs[i].line_count
        );
    }

    printf(
        "summary count=%d average_ms=%.3f median_ms=%.3f fastest_ms=%.3f slowest_ms=%.3f\n",
        sample_result->summary.count,
        sample_result->summary.average_ms,
        sample_result->summary.median_ms,
        sample_result->summary.fastest_ms,
        sample_result->summary.slowest_ms
    );
}

static void validate_samples(void) {
    int i;

    for (i = 0; i < SAMPLE_COUNT; i += 1) {
        FILE *file = fopen(SAMPLES[i].file, "r");
        if (file == NULL) {
            fprintf(stderr, "status=error\n");
            fprintf(stderr, "message=missing CSV file: %s. Run `python tools/create_sample_csv.py` first.\n", SAMPLES[i].file);
            exit(1);
        }
        fclose(file);
    }
}

static void write_results_array(FILE *output, const SampleResult sample_results[SAMPLE_COUNT]) {
    int sample_index;
    int run_index;
    int written = 0;

    fprintf(output, "  \"results\": [\n");

    for (sample_index = 0; sample_index < SAMPLE_COUNT; sample_index += 1) {
        for (run_index = 0; run_index < MEASURE_RUNS; run_index += 1) {
            const SampleResult *sample_result = &sample_results[sample_index];
            const RunResult *run = &sample_result->runs[run_index];

            if (written > 0) {
                fprintf(output, ",\n");
            }

            fprintf(output, "    {\n");
            fprintf(output, "      \"sample\": \"%s\",\n", sample_result->sample.name);
            fprintf(output, "      \"run\": %d,\n", run->run);
            fprintf(output, "      \"input_file\": \"%s\",\n", sample_result->sample.file);
            fprintf(output, "      \"rows\": %ld,\n", run->line_count);
            fprintf(output, "      \"elapsed_ms\": %.3f\n", run->elapsed_ms);
            fprintf(output, "    }");
            written += 1;
        }
    }

    fprintf(output, "\n  ],\n");
}

static void write_samples_array(FILE *output, const SampleResult sample_results[SAMPLE_COUNT]) {
    int sample_index;
    int run_index;

    fprintf(output, "  \"samples\": [\n");

    for (sample_index = 0; sample_index < SAMPLE_COUNT; sample_index += 1) {
        const SampleResult *sample_result = &sample_results[sample_index];
        const RunResult *last_run = &sample_result->runs[MEASURE_RUNS - 1];

        fprintf(output, "    {\n");
        fprintf(output, "      \"name\": \"%s\",\n", sample_result->sample.name);
        fprintf(output, "      \"input\": \"%s\",\n", sample_result->sample.file);
        fprintf(output, "      \"input_file\": \"%s\",\n", sample_result->sample.file);
        fprintf(output, "      \"input_file_size_bytes\": %ld,\n", sample_result->input_file_size_bytes);
        fprintf(output, "      \"expected\": {\n");
        fprintf(output, "        \"data_rows\": %ld\n", sample_result->sample.expected_data_rows);
        fprintf(output, "      },\n");
        fprintf(output, "      \"runs\": [\n");

        for (run_index = 0; run_index < MEASURE_RUNS; run_index += 1) {
            const RunResult *run = &sample_result->runs[run_index];

            fprintf(output, "        {\n");
            fprintf(output, "          \"run\": %d,\n", run->run);
            fprintf(output, "          \"elapsed_ms\": %.3f,\n", run->elapsed_ms);
            fprintf(output, "          \"metrics\": {\n");
            fprintf(output, "            \"line_count\": %ld\n", run->line_count);
            fprintf(output, "          }\n");
            fprintf(output, "        }%s\n", run_index == MEASURE_RUNS - 1 ? "" : ",");
        }

        fprintf(output, "      ],\n");
        fprintf(output, "      \"summary\": {\n");
        fprintf(output, "        \"count\": %d,\n", sample_result->summary.count);
        fprintf(output, "        \"average_ms\": %.3f,\n", sample_result->summary.average_ms);
        fprintf(output, "        \"median_ms\": %.3f,\n", sample_result->summary.median_ms);
        fprintf(output, "        \"fastest_ms\": %.3f,\n", sample_result->summary.fastest_ms);
        fprintf(output, "        \"slowest_ms\": %.3f\n", sample_result->summary.slowest_ms);
        fprintf(output, "      },\n");
        fprintf(output, "      \"line_count\": %ld,\n", last_run->line_count);
        fprintf(output, "      \"average_ms\": %.3f,\n", sample_result->summary.average_ms);
        fprintf(output, "      \"median_ms\": %.3f\n", sample_result->summary.median_ms);
        fprintf(output, "    }%s\n", sample_index == SAMPLE_COUNT - 1 ? "" : ",");
    }

    fprintf(output, "  ]\n");
}

static void write_result_json(const char *output_path, const SampleResult sample_results[SAMPLE_COUNT], const char *argv0) {
    FILE *output = fopen(output_path, "w");
    char created_at[32];

    if (output == NULL) {
        fprintf(stderr, "status=error\n");
        fprintf(stderr, "message=failed to open result file: %s (%s)\n", output_path, strerror(errno));
        exit(1);
    }

    build_timestamp(created_at, sizeof(created_at));

    fprintf(output, "{\n");
    fprintf(output, "  \"type\": \"langbench_result\",\n");
    fprintf(output, "  \"schema_version\": \"%s\",\n", SCHEMA_VERSION);
    fprintf(output, "  \"project\": \"%s\",\n", PROJECT);
    fprintf(output, "  \"experiment\": \"%s\",\n", EXPERIMENT);
    fprintf(output, "  \"experiment_label\": \"%s\",\n", EXPERIMENT_LABEL);
    fprintf(output, "  \"language\": \"%s\",\n", LANGUAGE);
    fprintf(output, "  \"created_at\": \"%s\",\n", created_at);
    fprintf(output, "  \"status\": \"success\",\n");
    fprintf(output, "  \"execution\": {\n");
    fprintf(output, "    \"runner\": \"%s\",\n", RUNNER);
    fprintf(output, "    \"runner_label\": \"%s\",\n", RUNNER_LABEL);
    fprintf(output, "    \"argv\": [\n");
    fprintf(output, "      ");
    write_json_string(output, argv0);
    fprintf(output, "\n");
    fprintf(output, "    ],\n");
    fprintf(output, "    \"command\": ");
    write_json_string(output, argv0);
    fprintf(output, ",\n");
    fprintf(output, "    \"script_path\": ");
    write_json_string(output, argv0);
    fprintf(output, "\n");
    fprintf(output, "  },\n");
    fprintf(output, "  \"runtime\": {\n");
    fprintf(output, "    \"name\": \"c\",\n");
    fprintf(output, "    \"version\": \"%s\"\n", runtime_standard());
    fprintf(output, "  },\n");
    fprintf(output, "  \"environment\": {\n");
    fprintf(output, "    \"os_name\": \"%s\",\n", os_name());
    fprintf(output, "    \"os_platform\": \"%s\",\n", os_platform());
    fprintf(output, "    \"memory_total_bytes\": null\n");
    fprintf(output, "  },\n");
    write_results_array(output, sample_results);
    write_samples_array(output, sample_results);
    fprintf(output, "}\n");

    if (fclose(output) != 0) {
        fprintf(stderr, "status=error\n");
        fprintf(stderr, "message=failed to close result file: %s\n", output_path);
        exit(1);
    }
}

int main(int argc, char *argv[]) {
    SampleResult sample_results[SAMPLE_COUNT];
    int sample_index;
    int run_index;
    const char *argv0 = argc > 0 ? argv[0] : "benchmarks/line_count/c/main";

    validate_samples();

    for (sample_index = 0; sample_index < SAMPLE_COUNT; sample_index += 1) {
        sample_results[sample_index].sample = SAMPLES[sample_index];
        sample_results[sample_index].input_file_size_bytes = get_file_size(SAMPLES[sample_index].file);

        for (run_index = 0; run_index < MEASURE_RUNS; run_index += 1) {
            sample_results[sample_index].runs[run_index] = measure_once(SAMPLES[sample_index].file, run_index + 1);
        }

        sample_results[sample_index].summary = summarize_runs(sample_results[sample_index].runs);
        print_sample_result(&sample_results[sample_index]);
    }

    write_result_json(RESULT_FILE, sample_results, argv0);
    printf("status=success\n");
    return 0;
}

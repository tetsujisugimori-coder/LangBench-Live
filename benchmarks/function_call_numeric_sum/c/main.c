#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <windows.h>

#define BENCHMARK "function_call_numeric_sum"
#define LANGUAGE "c"
#define ITEM_COUNT 1000000
#define WARMUP_ITERATIONS 5
#define MEASUREMENT_ITERATIONS 50
#define EXPECTED_CHECKSUM INT64_C(500000500000)
#define RESULT_FILE "results\\function_call_numeric_sum_c_result.json"
#define PATH_SIZE 4096

static LARGE_INTEGER timer_frequency;

static double round_ms(double value) { return (double)((int64_t)(value * 1000.0 + 0.5)) / 1000.0; }
static double now_ms(void) { LARGE_INTEGER counter; QueryPerformanceCounter(&counter); return (double)counter.QuadPart * 1000.0 / timer_frequency.QuadPart; }

static void write_json_string(FILE *out, const char *value) {
    const unsigned char *cursor = (const unsigned char *)value;
    fputc('"', out);
    while (*cursor) {
        switch (*cursor) {
            case '"': fputs("\\\"", out); break; case '\\': fputs("\\\\", out); break;
            case '\n': fputs("\\n", out); break; case '\r': fputs("\\r", out); break; case '\t': fputs("\\t", out); break;
            default: if (*cursor < 0x20) fprintf(out, "\\u%04x", *cursor); else fputc(*cursor, out);
        }
        cursor++;
    }
    fputc('"', out);
}

static int write_file_contents(FILE *out, const char *path) {
    char buffer[4096]; size_t count; FILE *input = fopen(path, "rb");
    if (!input) return 0;
    while ((count = fread(buffer, 1, sizeof(buffer), input)) > 0) {
        if (fwrite(buffer, 1, count, out) != count) { fclose(input); return 0; }
    }
    if (ferror(input)) { fclose(input); return 0; }
    fclose(input); return 1;
}

static void local_iso_timestamp(char *buffer, size_t size) {
    time_t now = time(NULL); struct tm local_time; char date[32]; TIME_ZONE_INFORMATION zone; DWORD id; LONG bias; int offset;
    localtime_s(&local_time, &now); strftime(date, sizeof(date), "%Y-%m-%dT%H:%M:%S", &local_time);
    id = GetTimeZoneInformation(&zone); bias = zone.Bias;
    if (id == TIME_ZONE_ID_STANDARD) bias += zone.StandardBias;
    if (id == TIME_ZONE_ID_DAYLIGHT) bias += zone.DaylightBias;
    offset = -(int)bias;
    snprintf(buffer, size, "%s%c%02d:%02d", date, offset >= 0 ? '+' : '-', abs(offset) / 60, abs(offset) % 60);
}

static void timestamp_id(char *buffer, size_t size) {
    SYSTEMTIME time; GetLocalTime(&time);
    snprintf(buffer, size, "%04u%02u%02u_%02u%02u%02u", time.wYear, time.wMonth, time.wDay, time.wHour, time.wMinute, time.wSecond);
}

static const char *architecture_name(WORD architecture) {
    switch (architecture) {
        case PROCESSOR_ARCHITECTURE_AMD64: return "x64"; case PROCESSOR_ARCHITECTURE_ARM64: return "arm64";
        case PROCESSOR_ARCHITECTURE_INTEL: return "x86"; case PROCESSOR_ARCHITECTURE_ARM: return "arm"; default: return NULL;
    }
}

static void cpu_model(char *buffer, DWORD size) {
    HKEY key = NULL; DWORD type = 0;
    buffer[0] = '\0';
    if (RegOpenKeyExA(HKEY_LOCAL_MACHINE, "HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0", 0, KEY_READ, &key) == ERROR_SUCCESS) {
        RegQueryValueExA(key, "ProcessorNameString", NULL, &type, (LPBYTE)buffer, &size); RegCloseKey(key);
    }
}

static int compare_double(const void *left, const void *right) {
    double a = *(const double *)left, b = *(const double *)right; return (a > b) - (a < b);
}

static int64_t direct_sum(const int32_t *values) {
    int64_t total = 0; size_t index; for (index = 0; index < ITEM_COUNT; index++) total += values[index]; return total;
}

#if defined(_MSC_VER)
#define NOINLINE __declspec(noinline)
#elif defined(__GNUC__) || defined(__clang__)
#define NOINLINE __attribute__((noinline))
#else
#define NOINLINE
#endif
static NOINLINE int64_t add(int64_t current, int32_t value) { return current + value; }
static int64_t function_call_sum(const int32_t *values) {
    int64_t total = 0; size_t index; for (index = 0; index < ITEM_COUNT; index++) total = add(total, values[index]); return total;
}

static int measure(const int32_t *values, int64_t (*case_sum)(const int32_t *), double *warmup_ms, double samples[MEASUREMENT_ITERATIONS], int64_t *checksum) {
    int iteration; double start;
    start = now_ms();
    for (iteration = 0; iteration < WARMUP_ITERATIONS; iteration++) if (case_sum(values) != EXPECTED_CHECKSUM) return 0;
    *warmup_ms = round_ms(now_ms() - start);
    for (iteration = 0; iteration < MEASUREMENT_ITERATIONS; iteration++) {
        start = now_ms(); *checksum = case_sum(values); samples[iteration] = round_ms(now_ms() - start);
        if (*checksum != EXPECTED_CHECKSUM) return 0;
    }
    return 1;
}

static double sample_total(const double samples[MEASUREMENT_ITERATIONS]) {
    double total = 0; int index; for (index = 0; index < MEASUREMENT_ITERATIONS; index++) total += samples[index]; return round_ms(total);
}

static void write_case(FILE *out, const double samples[MEASUREMENT_ITERATIONS]) {
    double sorted[MEASUREMENT_ITERATIONS], total = 0; int index;
    for (index = 0; index < MEASUREMENT_ITERATIONS; index++) { sorted[index] = samples[index]; total += samples[index]; }
    qsort(sorted, MEASUREMENT_ITERATIONS, sizeof(sorted[0]), compare_double);
    fprintf(out, "{\n      \"samples_ms\": [");
    for (index = 0; index < MEASUREMENT_ITERATIONS; index++) fprintf(out, "%.3f%s", samples[index], index + 1 == MEASUREMENT_ITERATIONS ? "" : ",");
    fprintf(out, "],\n      \"min_ms\": %.3f,\n      \"max_ms\": %.3f,\n      \"mean_ms\": %.3f,\n      \"median_ms\": %.3f\n    }",
        sorted[0], sorted[MEASUREMENT_ITERATIONS - 1], round_ms(total / MEASUREMENT_ITERATIONS),
        round_ms((sorted[MEASUREMENT_ITERATIONS / 2 - 1] + sorted[MEASUREMENT_ITERATIONS / 2]) / 2.0));
}

static int optional_arg(int argc, char *argv[], const char *prefix, char *output, size_t output_size) {
    size_t prefix_length = strlen(prefix); int index;
    for (index = 5; index < argc; index++) if (strncmp(argv[index], prefix, prefix_length) == 0) {
        strncpy(output, argv[index] + prefix_length, output_size - 1); output[output_size - 1] = '\0'; return 1;
    }
    return 0;
}

int main(int argc, char *argv[]) {
    double compile_ms, setup_start, setup_ms, direct_warmup, call_warmup, direct_samples[MEASUREMENT_ITERATIONS], call_samples[MEASUREMENT_ITERATIONS], measurement_ms;
    int32_t *values = NULL; int64_t direct_checksum = 0, call_checksum = 0; char experiment_id[256] = "", run_id[256] = "", created_at[48], cwd[PATH_SIZE], cpu[256] = "", output_path[PATH_SIZE];
    SYSTEM_INFO system; MEMORYSTATUSEX memory; FILE *out; size_t index;
    if (argc < 6 || sscanf(argv[1], "%lf", &compile_ms) != 1 || compile_ms < 0 || !argv[2][0] || !argv[3][0] || !argv[4][0] || !argv[5][0]) {
        fprintf(stderr, "status=error\nmessage=expected build and optimization analysis arguments\n"); return 1;
    }
    if (!QueryPerformanceFrequency(&timer_frequency) || timer_frequency.QuadPart == 0) { fprintf(stderr, "status=error\nmessage=high-resolution timer is unavailable\n"); return 1; }
    if (!optional_arg(argc, argv, "--experiment-id=", experiment_id, sizeof(experiment_id))) {
        const char *value = getenv("LANGBENCH_EXPERIMENT_ID"); if (value) strncpy(experiment_id, value, sizeof(experiment_id) - 1);
    }
    if (!optional_arg(argc, argv, "--run-id=", run_id, sizeof(run_id))) {
        const char *value = getenv("LANGBENCH_RUN_ID"); if (value) strncpy(run_id, value, sizeof(run_id) - 1);
    }
    if (!experiment_id[0]) { char timestamp[64]; timestamp_id(timestamp, sizeof(timestamp)); snprintf(experiment_id, sizeof(experiment_id), "%s_%s", timestamp, BENCHMARK); }
    if (!run_id[0]) { char timestamp[64]; timestamp_id(timestamp, sizeof(timestamp)); snprintf(run_id, sizeof(run_id), "%s_%s_%s", timestamp, LANGUAGE, BENCHMARK); }
    setup_start = now_ms();
    values = malloc((size_t)ITEM_COUNT * sizeof(*values));
    if (!values) { fprintf(stderr, "status=error\nmessage=failed to allocate array\n"); return 1; }
    for (index = 0; index < ITEM_COUNT; index++) values[index] = (int32_t)(index + 1);
    setup_ms = round_ms(now_ms() - setup_start);
    if (!measure(values, direct_sum, &direct_warmup, direct_samples, &direct_checksum) || !measure(values, function_call_sum, &call_warmup, call_samples, &call_checksum)) {
        free(values); fprintf(stderr, "status=error\nmessage=checksum mismatch\n"); return 1;
    }
    measurement_ms = round_ms(sample_total(direct_samples) + sample_total(call_samples));
    if (!GetCurrentDirectoryA(sizeof(cwd), cwd)) { free(values); fprintf(stderr, "status=error\nmessage=failed to get cwd\n"); return 1; }
    if (strlen(cwd) + 1 + strlen(RESULT_FILE) + 1 > sizeof(output_path)) {
        free(values); fprintf(stderr, "status=error\nmessage=result path is too long\n"); return 1;
    }
    strcpy(output_path, cwd); strcat(output_path, "\\"); strcat(output_path, RESULT_FILE);
    local_iso_timestamp(created_at, sizeof(created_at)); cpu_model(cpu, sizeof(cpu)); GetNativeSystemInfo(&system);
    memory.dwLength = sizeof(memory); if (!GlobalMemoryStatusEx(&memory)) memory.ullTotalPhys = 0;
    out = fopen(output_path, "wb"); if (!out) { free(values); fprintf(stderr, "status=error\nmessage=failed to open result: %s\n", strerror(errno)); return 1; }
    fprintf(out, "{\n  \"type\": \"langbench_result\",\n  \"schema_version\": \"1.0\",\n  \"project\": \"LangBench Live\",\n  \"benchmark\": \"%s\",\n  \"experiment_id\": ", BENCHMARK); write_json_string(out, experiment_id);
    fprintf(out, ",\n  \"run_id\": "); write_json_string(out, run_id); fprintf(out, ",\n  \"language\": \"c\",\n  \"created_at\": "); write_json_string(out, created_at);
    fprintf(out, ",\n  \"status\": \"success\",\n  \"engine\": {\"runtime\": \"native\", \"runtime_version\": null},\n  \"execution\": {\"runner\": \"vscode_terminal_powershell\", \"runner_label\": \"VSCode Terminal / PowerShell\", \"cwd\": "); write_json_string(out, cwd); fprintf(out, ", \"argv\": [");
    for (int i = 0; i < argc; i++) { write_json_string(out, argv[i]); fprintf(out, "%s", i + 1 == argc ? "" : ", "); }
    fprintf(out, "]},\n  \"environment\": {\"os\": \"Windows\", \"os_version\": null, \"architecture\": "); if (architecture_name(system.wProcessorArchitecture)) write_json_string(out, architecture_name(system.wProcessorArchitecture)); else fputs("null", out);
    fprintf(out, ", \"cpu\": "); if (cpu[0]) write_json_string(out, cpu); else fputs("null", out); fprintf(out, ", \"logical_processors\": %lu, \"memory_bytes\": ", system.dwNumberOfProcessors); if (memory.ullTotalPhys) fprintf(out, "%" PRIu64, (uint64_t)memory.ullTotalPhys); else fputs("null", out);
    fprintf(out, "},\n  \"build\": {\"required\": true, \"compiler\": \"gcc\", \"compiler_version\": "); write_json_string(out, argv[2]); fprintf(out, ", \"compile_command\": "); write_json_string(out, argv[3]); fprintf(out, ", \"compile_ms\": %.3f, \"source_path\": ", compile_ms); write_json_string(out, argv[4]);
    fprintf(out, "},\n  \"optimization_analysis\": ");
    if (!write_file_contents(out, argv[5])) { fclose(out); free(values); fprintf(stderr, "status=error\nmessage=failed to read optimization analysis JSON\n"); return 1; }
    fprintf(out, ",\n");
    fprintf(out, "  \"config\": {\"item_count\": %d, \"warmup_iterations\": %d, \"measurement_iterations\": %d, \"numeric_type\": \"integer\", \"value_field\": \"value\", \"cases\": [\"direct\", \"function_call\"]},\n  \"timing\": {\"process_startup_ms\": null, \"setup_ms\": %.3f, \"warmup_ms\": %.3f, \"measurement_ms\": %.3f, \"benchmark_total_ms\": %.3f},\n  \"results\": {\"direct\": ", ITEM_COUNT, WARMUP_ITERATIONS, MEASUREMENT_ITERATIONS, setup_ms, round_ms(direct_warmup + call_warmup), measurement_ms, round_ms(setup_ms + direct_warmup + call_warmup + measurement_ms));
    write_case(out, direct_samples); fprintf(out, ", \"function_call\": "); write_case(out, call_samples);
    fprintf(out, "},\n  \"validation\": {\"direct_checksum\": %" PRId64 ", \"function_call_checksum\": %" PRId64 ", \"expected_checksum\": %" PRId64 ", \"tolerance\": 0, \"passed\": true},\n  \"error\": null\n}\n", direct_checksum, call_checksum, EXPECTED_CHECKSUM);
    int write_failed = ferror(out);
    if (fclose(out) != 0) {
        write_failed = 1;
    }
    if (write_failed) {
        free(values);
        fprintf(stderr, "status=error\nmessage=failed to finish writing result JSON\n");
        return 1;
    }
    free(values);
    puts("status=success");
    return 0;
}

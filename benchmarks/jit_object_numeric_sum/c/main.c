#include <errno.h>
#include <inttypes.h>
#include <locale.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <windows.h>

#define PROJECT "LangBench Live"
#define SCHEMA_VERSION "1.0"
#define LANGUAGE "c"
#define BENCHMARK "jit_object_numeric_sum"
#define ARRAY_SIZE 1000000
#define ITERATIONS 50
#define WARMUP_ITERATIONS 5
#define EXPECTED_CHECKSUM INT64_C(500000500000)
#define RESULT_FILE "results\\jit_object_numeric_sum_c_result.json"
#define RUNNER "vscode_terminal_powershell"
#define RUNNER_LABEL "VSCode Terminal / PowerShell"
#define PATH_BUFFER_SIZE 4096

typedef struct {
    double elapsed_ms;
} IterationResult;

typedef struct {
    int32_t value;
} Item;

static LARGE_INTEGER timer_frequency;

static double round_ms(double value) {
    return (double)((int64_t)(value * 1000.0 + 0.5)) / 1000.0;
}

static double now_ms(void) {
    LARGE_INTEGER counter;
    QueryPerformanceCounter(&counter);
    return (double)counter.QuadPart * 1000.0 / (double)timer_frequency.QuadPart;
}

static void write_json_string(FILE *output, const char *value) {
    const unsigned char *cursor = (const unsigned char *)value;
    fputc('"', output);
    while (*cursor != '\0') {
        switch (*cursor) {
            case '"': fputs("\\\"", output); break;
            case '\\': fputs("\\\\", output); break;
            case '\b': fputs("\\b", output); break;
            case '\f': fputs("\\f", output); break;
            case '\n': fputs("\\n", output); break;
            case '\r': fputs("\\r", output); break;
            case '\t': fputs("\\t", output); break;
            default:
                if (*cursor < 0x20) {
                    fprintf(output, "\\u%04x", *cursor);
                } else {
                    fputc(*cursor, output);
                }
                break;
        }
        cursor++;
    }
    fputc('"', output);
}

static int compare_double(const void *left, const void *right) {
    double a = *(const double *)left;
    double b = *(const double *)right;
    return (a > b) - (a < b);
}

static void local_iso_timestamp(char *buffer, size_t size) {
    time_t now = time(NULL);
    struct tm local_time;
    char date[32];
    TIME_ZONE_INFORMATION timezone;
    DWORD timezone_id;
    LONG bias;
    int offset_minutes;
    char sign;
    localtime_s(&local_time, &now);
    strftime(date, sizeof(date), "%Y-%m-%dT%H:%M:%S", &local_time);
    timezone_id = GetTimeZoneInformation(&timezone);
    bias = timezone.Bias;
    if (timezone_id == TIME_ZONE_ID_STANDARD) bias += timezone.StandardBias;
    if (timezone_id == TIME_ZONE_ID_DAYLIGHT) bias += timezone.DaylightBias;
    offset_minutes = (int)-bias;
    sign = offset_minutes >= 0 ? '+' : '-';
    if (offset_minutes < 0) offset_minutes = -offset_minutes;
    snprintf(buffer, size, "%s%c%02d:%02d", date, sign, offset_minutes / 60, offset_minutes % 60);
}

static void cpu_model(char *buffer, DWORD size) {
    HKEY key = NULL;
    DWORD type = 0;
    if (RegOpenKeyExA(HKEY_LOCAL_MACHINE,
            "HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0", 0, KEY_READ, &key) != ERROR_SUCCESS ||
        RegQueryValueExA(key, "ProcessorNameString", NULL, &type, (LPBYTE)buffer, &size) != ERROR_SUCCESS) {
        buffer[0] = '\0';
    }
    if (key != NULL) {
        RegCloseKey(key);
    }
}

static void os_version(char *buffer, size_t size) {
    (void)size;
    buffer[0] = '\0';
}

static const char *architecture_name(WORD architecture) {
    switch (architecture) {
        case PROCESSOR_ARCHITECTURE_AMD64: return "x64";
        case PROCESSOR_ARCHITECTURE_ARM64: return "arm64";
        case PROCESSOR_ARCHITECTURE_INTEL: return "x86";
        case PROCESSOR_ARCHITECTURE_ARM: return "arm";
        default: return NULL;
    }
}

static void build_timestamp_id(char *buffer, size_t size) {
    SYSTEMTIME st;
    GetLocalTime(&st);
    snprintf(
        buffer,
        size,
        "%04d%02d%02d_%02d%02d%02d",
        st.wYear,
        st.wMonth,
        st.wDay,
        st.wHour,
        st.wMinute,
        st.wSecond
    );
}

static void build_run_id(char *buffer, size_t size) {
    SYSTEMTIME st;
    GetLocalTime(&st);
    snprintf(
        buffer,
        size,
        "%04d%02d%02d_%02d%02d%02d_%s_%s",
        st.wYear,
        st.wMonth,
        st.wDay,
        st.wHour,
        st.wMinute,
        st.wSecond,
        LANGUAGE,
        BENCHMARK
    );
}

static int get_optional_arg_value(int argc, char *argv[], const char *prefix, char *output, size_t output_size) {
    size_t prefix_length = strlen(prefix);
    for (int index = 5; index < argc; index++) {
        if (strncmp(argv[index], prefix, prefix_length) == 0) {
            strncpy(output, argv[index] + prefix_length, output_size - 1);
            output[output_size - 1] = '\0';
            return 1;
        }
    }
    return 0;
}

static void get_experiment_and_run_id(int argc, char *argv[], char *experiment_id, size_t experiment_size, char *run_id, size_t run_size) {
    experiment_id[0] = '\0';
    run_id[0] = '\0';

    if (!get_optional_arg_value(argc, argv, "--experiment-id=", experiment_id, experiment_size)) {
        const char *env_experiment_id = getenv("LANGBENCH_EXPERIMENT_ID");
        if (env_experiment_id != NULL) {
            strncpy(experiment_id, env_experiment_id, experiment_size - 1);
            experiment_id[experiment_size - 1] = '\0';
        }
    }

    if (!get_optional_arg_value(argc, argv, "--run-id=", run_id, run_size)) {
        const char *env_run_id = getenv("LANGBENCH_RUN_ID");
        if (env_run_id != NULL) {
            strncpy(run_id, env_run_id, run_size - 1);
            run_id[run_size - 1] = '\0';
        }
    }

    if (experiment_id[0] == '\0') {
        char generated_experiment[128];
        build_timestamp_id(generated_experiment, sizeof(generated_experiment));
        snprintf(experiment_id, experiment_size, "%s_%s", generated_experiment, BENCHMARK);
    }

    if (run_id[0] == '\0') {
        build_run_id(run_id, run_size);
    }
}

static int64_t sum_items(const Item *values, size_t count) {
    int64_t total = 0;
    for (size_t index = 0; index < count; index++) {
        total += values[index].value;
    }
    return total;
}

int main(int argc, char *argv[]) {
    Item *values = NULL;
    IterationResult results[ITERATIONS];
    double sorted[ITERATIONS];
    double total_ms = 0.0;
    double compile_ms;
    double setup_start;
    double setup_ms;
    double warmup_start;
    double warmup_ms;
    double measurement_ms;
    double benchmark_total_ms;
    char cwd[PATH_BUFFER_SIZE];
    char output_path[PATH_BUFFER_SIZE];
    char created_at[48];
    char cpu_name[256] = "";
    char version[64] = "";
    char experiment_id[256];
    char run_id[256];
    SYSTEM_INFO system_info;
    MEMORYSTATUSEX memory;
    FILE *output;
    size_t index;
    int iteration;

    setlocale(LC_NUMERIC, "C");
    if (argc < 5 || sscanf(argv[1], "%lf", &compile_ms) != 1 || compile_ms < 0.0) {
        fprintf(stderr, "status=error\nmessage=expected compile_ms, compiler version, compile command, and source path\n");
        return 1;
    }
    (void)compile_ms;

    get_experiment_and_run_id(argc, argv, experiment_id, sizeof(experiment_id), run_id, sizeof(run_id));

    if (!QueryPerformanceFrequency(&timer_frequency) || timer_frequency.QuadPart == 0) {
        fprintf(stderr, "status=error\nmessage=high-resolution timer is unavailable\n");
        return 1;
    }

    if (ARRAY_SIZE > SIZE_MAX / sizeof(*values)) {
        fprintf(stderr, "status=error\nmessage=array size overflow\n");
        return 1;
    }

    setup_start = now_ms();
    values = (Item *)malloc((size_t)ARRAY_SIZE * sizeof(*values));
    if (values == NULL) {
        fprintf(stderr, "status=error\nmessage=failed to allocate array\n");
        return 1;
    }

    for (index = 0; index < ARRAY_SIZE; index++) {
        values[index].value = (int32_t)(index + 1);
    }
    setup_ms = round_ms(now_ms() - setup_start);

    warmup_start = now_ms();
    for (iteration = 0; iteration < WARMUP_ITERATIONS; iteration++) {
        int64_t checksum = sum_items(values, ARRAY_SIZE);
        if (checksum != EXPECTED_CHECKSUM) {
            free(values);
            fprintf(stderr, "status=error\nmessage=warmup checksum mismatch\n");
            return 1;
        }
    }
    warmup_ms = round_ms(now_ms() - warmup_start);

    total_ms = 0.0;
    for (iteration = 0; iteration < ITERATIONS; iteration++) {
        double start = now_ms();
        int64_t checksum = sum_items(values, ARRAY_SIZE);
        double elapsed = round_ms(now_ms() - start);
        if (checksum != EXPECTED_CHECKSUM) {
            free(values);
            fprintf(stderr, "status=error\nmessage=checksum mismatch\n");
            return 1;
        }
        results[iteration].elapsed_ms = elapsed;
        sorted[iteration] = elapsed;
        total_ms += elapsed;
    }
    measurement_ms = round_ms(total_ms);
    benchmark_total_ms = round_ms(setup_ms + warmup_ms + measurement_ms);
    free(values);
    qsort(sorted, ITERATIONS, sizeof(sorted[0]), compare_double);

    if (GetCurrentDirectoryA(sizeof(cwd), cwd) == 0) {
        fprintf(stderr, "status=error\nmessage=failed to obtain execution paths\n");
        return 1;
    }
    if (strlen(cwd) + 1 + strlen(RESULT_FILE) + 1 > sizeof(output_path)) {
        fprintf(stderr, "status=error\nmessage=result path is too long\n");
        return 1;
    }
    strcpy(output_path, cwd);
    strcat(output_path, "\\");
    strcat(output_path, RESULT_FILE);
    local_iso_timestamp(created_at, sizeof(created_at));
    cpu_model(cpu_name, sizeof(cpu_name));
    os_version(version, sizeof(version));
    GetNativeSystemInfo(&system_info);
    memory.dwLength = sizeof(memory);
    if (!GlobalMemoryStatusEx(&memory)) {
        memory.ullTotalPhys = 0;
    }

    output = fopen(output_path, "wb");
    if (output == NULL) {
        fprintf(stderr, "status=error\nmessage=failed to open result file: %s\n", strerror(errno));
        return 1;
    }

    fprintf(output, "{\n");
    fprintf(output, "  \"type\": \"langbench_result\",\n");
    fprintf(output, "  \"schema_version\": \"%s\",\n", SCHEMA_VERSION);
    fprintf(output, "  \"project\": \"%s\",\n", PROJECT);
    fprintf(output, "  \"benchmark\": \"%s\",\n", BENCHMARK);
    fprintf(output, "  \"experiment_id\": "); write_json_string(output, experiment_id); fprintf(output, ",\n");
    fprintf(output, "  \"run_id\": "); write_json_string(output, run_id); fprintf(output, ",\n");
    fprintf(output, "  \"language\": \"%s\",\n", LANGUAGE);
    fprintf(output, "  \"created_at\": "); write_json_string(output, created_at); fprintf(output, ",\n");
    fprintf(output, "  \"status\": \"success\",\n");
    fprintf(output, "  \"engine\": {\n    \"runtime\": \"native\",\n    \"runtime_version\": null,\n    \"compiler\": \"gcc\",\n    \"compiler_version\": "); write_json_string(output, argv[2]); fprintf(output, "\n  },\n");
    fprintf(output, "  \"execution\": {\n    \"runner\": \"%s\",\n    \"runner_label\": \"%s\",\n    \"cwd\": ", RUNNER, RUNNER_LABEL); write_json_string(output, cwd); fprintf(output, ",\n");
    fprintf(output, "    \"argv\": [\n");
    for (iteration = 0; iteration < argc; iteration++) {
        fprintf(output, "      "); write_json_string(output, argv[iteration]);
        fprintf(output, "%s\n", iteration == argc - 1 ? "" : ",");
    }
    fprintf(output, "    ]\n  },\n");
    fprintf(output, "  \"environment\": {\n    \"os\": \"Windows\",\n    \"os_version\": ");
    if (version[0] == '\0') fputs("null", output); else write_json_string(output, version);
    fprintf(output, ",\n    \"architecture\": ");
    if (architecture_name(system_info.wProcessorArchitecture) == NULL) fputs("null", output); else write_json_string(output, architecture_name(system_info.wProcessorArchitecture));
    fprintf(output, ",\n    \"cpu\": ");
    if (cpu_name[0] == '\0') fputs("null", output); else write_json_string(output, cpu_name);
    fprintf(output, ",\n    \"logical_processors\": %lu,\n    \"memory_bytes\": ", system_info.dwNumberOfProcessors);
    if (memory.ullTotalPhys == 0) fputs("null", output); else fprintf(output, "%" PRIu64, (uint64_t)memory.ullTotalPhys);
    fprintf(output, "\n  },\n");
    fprintf(output, "  \"config\": {\n    \"item_count\": %d,\n    \"warmup_iterations\": %d,\n    \"measurement_iterations\": %d,\n    \"numeric_type\": \"integer\",\n    \"value_field\": \"value\"\n  },\n", ARRAY_SIZE, WARMUP_ITERATIONS, ITERATIONS);
    fprintf(output, "  \"timing\": {\n    \"process_startup_ms\": null,\n    \"setup_ms\": %.3f,\n    \"warmup_ms\": %.3f,\n    \"measurement_ms\": %.3f,\n    \"benchmark_total_ms\": %.3f\n  },\n", setup_ms, warmup_ms, measurement_ms, benchmark_total_ms);
    fprintf(output, "  \"results\": {\n    \"samples_ms\": [\n");
    for (iteration = 0; iteration < ITERATIONS; iteration++) {
        fprintf(output, "      %.3f%s\n", results[iteration].elapsed_ms, iteration == ITERATIONS - 1 ? "" : ",");
    }
    fprintf(output, "    ],\n    \"min_ms\": %.3f,\n    \"max_ms\": %.3f,\n    \"mean_ms\": %.3f,\n    \"median_ms\": %.3f\n  },\n",
        sorted[0],
        sorted[ITERATIONS - 1],
        round_ms(total_ms / ITERATIONS),
        round_ms((sorted[ITERATIONS / 2 - 1] + sorted[ITERATIONS / 2]) / 2.0));
    fprintf(output, "  \"validation\": {\n    \"checksum\": %" PRId64 ",\n    \"expected_checksum\": %" PRId64 ",\n    \"tolerance\": 0,\n    \"passed\": true\n  },\n", EXPECTED_CHECKSUM, EXPECTED_CHECKSUM);
    fprintf(output, "  \"error\": null\n}\n");

    if (fclose(output) != 0) {
        fprintf(stderr, "status=error\nmessage=failed to close result file\n");
        return 1;
    }

    printf("status=success\n");
    return 0;
}

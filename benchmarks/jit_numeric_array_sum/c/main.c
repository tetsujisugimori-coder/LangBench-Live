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
#define BENCHMARK "jit_numeric_array_sum"
#define ARRAY_SIZE 1000000
#define ITERATIONS 50
#define EXPECTED_CHECKSUM INT64_C(499999500000)
#define RESULT_FILE "results\\jit_numeric_array_sum_c_result.json"
#define RUNNER "vscode_terminal_powershell"
#define RUNNER_LABEL "VSCode Terminal / PowerShell"
#define PATH_BUFFER_SIZE 4096

typedef struct {
    int iteration;
    double elapsed_ms;
    int64_t checksum;
} IterationResult;

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
    char zone[8];
    localtime_s(&local_time, &now);
    strftime(date, sizeof(date), "%Y-%m-%dT%H:%M:%S", &local_time);
    strftime(zone, sizeof(zone), "%z", &local_time);
    if (strlen(zone) == 5) {
        snprintf(buffer, size, "%s%c%c%c:%c%c", date, zone[0], zone[1], zone[2], zone[3], zone[4]);
    } else {
        snprintf(buffer, size, "%s", date);
    }
}

static void cpu_model(char *buffer, DWORD size) {
    HKEY key = NULL;
    DWORD type = 0;
    if (RegOpenKeyExA(HKEY_LOCAL_MACHINE,
            "HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0", 0, KEY_READ, &key) != ERROR_SUCCESS ||
        RegQueryValueExA(key, "ProcessorNameString", NULL, &type, (LPBYTE)buffer, &size) != ERROR_SUCCESS) {
        snprintf(buffer, size, "unknown");
    }
    if (key != NULL) {
        RegCloseKey(key);
    }
}

static void os_version(char *buffer, size_t size) {
    snprintf(buffer, size, "unknown");
}

static int64_t sum_array(const int *values, size_t count) {
    size_t index;
    int64_t total = 0;
    for (index = 0; index < count; index++) {
        total += values[index];
    }
    return total;
}

int main(int argc, char *argv[]) {
    int *values = NULL;
    IterationResult results[ITERATIONS];
    double sorted[ITERATIONS];
    double total_ms = 0.0;
    double compile_ms;
    double setup_start;
    double setup_ms;
    char cwd[PATH_BUFFER_SIZE];
    char exe_path[PATH_BUFFER_SIZE];
    char output_path[PATH_BUFFER_SIZE];
    char created_at[48];
    char cpu_name[256] = "unknown";
    char version[64];
    SYSTEM_INFO system_info;
    MEMORYSTATUSEX memory;
    FILE *output;
    size_t index;
    int iteration;

    setlocale(LC_NUMERIC, "C");
    if (argc != 5 || sscanf(argv[1], "%lf", &compile_ms) != 1 || compile_ms < 0.0) {
        fprintf(stderr, "status=error\nmessage=expected compile_ms, compiler version, compile command, and source path\n");
        return 1;
    }
    if (!QueryPerformanceFrequency(&timer_frequency) || timer_frequency.QuadPart == 0) {
        fprintf(stderr, "status=error\nmessage=high-resolution timer is unavailable\n");
        return 1;
    }
    if (ARRAY_SIZE > SIZE_MAX / sizeof(*values)) {
        fprintf(stderr, "status=error\nmessage=array size overflow\n");
        return 1;
    }

    setup_start = now_ms();
    values = (int *)malloc((size_t)ARRAY_SIZE * sizeof(*values));
    if (values == NULL) {
        fprintf(stderr, "status=error\nmessage=failed to allocate array\n");
        return 1;
    }
    for (index = 0; index < ARRAY_SIZE; index++) {
        values[index] = (int)index;
    }
    setup_ms = round_ms(now_ms() - setup_start);

    for (iteration = 0; iteration < ITERATIONS; iteration++) {
        double start = now_ms();
        int64_t checksum = sum_array(values, ARRAY_SIZE);
        double elapsed = round_ms(now_ms() - start);
        if (checksum != EXPECTED_CHECKSUM) {
            free(values);
            fprintf(stderr, "status=error\nmessage=checksum mismatch\n");
            return 1;
        }
        results[iteration].iteration = iteration + 1;
        results[iteration].elapsed_ms = elapsed;
        results[iteration].checksum = checksum;
        sorted[iteration] = elapsed;
        total_ms += elapsed;
    }
    free(values);
    qsort(sorted, ITERATIONS, sizeof(sorted[0]), compare_double);

    if (GetCurrentDirectoryA(sizeof(cwd), cwd) == 0 ||
        GetModuleFileNameA(NULL, exe_path, sizeof(exe_path)) == 0) {
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
    GetSystemInfo(&system_info);
    memory.dwLength = sizeof(memory);
    if (!GlobalMemoryStatusEx(&memory)) {
        memory.ullTotalPhys = 0;
    }

    output = fopen(output_path, "wb");
    if (output == NULL) {
        fprintf(stderr, "status=error\nmessage=failed to open result file: %s\n", strerror(errno));
        return 1;
    }
    fprintf(output, "{\n  \"type\": \"langbench_result\",\n  \"schema_version\": \"%s\",\n", SCHEMA_VERSION);
    fprintf(output, "  \"project\": \"%s\",\n  \"benchmark\": \"%s\",\n  \"experiment\": \"%s\",\n", PROJECT, BENCHMARK, BENCHMARK);
    fprintf(output, "  \"language\": \"c\",\n  \"created_at\": "); write_json_string(output, created_at);
    fprintf(output, ",\n  \"status\": \"success\",\n  \"engine\": {\"runtime\": \"native\", \"compiler\": \"gcc\"},\n");
    fprintf(output, "  \"execution\": {\n    \"runner\": \"%s\",\n    \"runner_label\": \"%s\",\n    \"cwd\": ", RUNNER, RUNNER_LABEL);
    write_json_string(output, cwd);
    fprintf(output, ",\n    \"argv\": [");
    for (iteration = 0; iteration < argc; iteration++) {
        if (iteration > 0) fputs(", ", output);
        write_json_string(output, argv[iteration]);
    }
    fprintf(output, "],\n    \"command\": "); write_json_string(output, exe_path);
    fprintf(output, ",\n    \"script_path\": "); write_json_string(output, argv[4]);
    fprintf(output, "\n  },\n  \"runtime\": {\"name\": \"native\", \"version\": null},\n");
    fprintf(output, "  \"build\": {\n    \"required\": true,\n    \"compiler\": \"gcc\",\n    \"compiler_version\": ");
    write_json_string(output, argv[2]);
    fprintf(output, ",\n    \"compile_command\": "); write_json_string(output, argv[3]);
    fprintf(output, ",\n    \"compile_ms\": %.3f\n  },\n", compile_ms);
    fprintf(output, "  \"environment\": {\n    \"os_name\": \"Windows\",\n    \"os_platform\": \"win32\",\n    \"os_version\": ");
    write_json_string(output, version);
    fprintf(output, ",\n    \"cpu_model\": "); write_json_string(output, cpu_name);
    fprintf(output, ",\n    \"cpu_threads\": %lu,\n    \"memory_total_bytes\": %" PRIu64 "\n  },\n",
        system_info.dwNumberOfProcessors, (uint64_t)memory.ullTotalPhys);
    fprintf(output, "  \"output_file\": "); write_json_string(output, output_path);
    fprintf(output, ",\n  \"array_size\": %d,\n  \"iterations\": %d,\n  \"setup_ms\": %.3f,\n  \"results\": [\n",
        ARRAY_SIZE, ITERATIONS, setup_ms);
    for (iteration = 0; iteration < ITERATIONS; iteration++) {
        fprintf(output, "    {\"iteration\": %d, \"elapsed_ms\": %.3f, \"checksum\": %" PRId64 "}%s\n",
            results[iteration].iteration, results[iteration].elapsed_ms, results[iteration].checksum,
            iteration == ITERATIONS - 1 ? "" : ",");
    }
    fprintf(output, "  ],\n  \"summary\": {\n    \"count\": %d,\n    \"average_ms\": %.3f,\n",
        ITERATIONS, round_ms(total_ms / ITERATIONS));
    fprintf(output, "    \"median_ms\": %.3f,\n    \"fastest_ms\": %.3f,\n    \"slowest_ms\": %.3f\n  }\n}\n",
        round_ms((sorted[ITERATIONS / 2 - 1] + sorted[ITERATIONS / 2]) / 2.0),
        sorted[0], sorted[ITERATIONS - 1]);
    if (fclose(output) != 0) {
        fprintf(stderr, "status=error\nmessage=failed to close result file\n");
        return 1;
    }
    printf("status=success\n");
    return 0;
}

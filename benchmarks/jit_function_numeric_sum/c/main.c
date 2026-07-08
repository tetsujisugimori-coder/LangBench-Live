#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#if defined(_WIN32)
#include <direct.h>
#include <windows.h>
#else
#include <unistd.h>
#endif

#define PROJECT "LangBench Live"
#define SCHEMA_VERSION "1.0"
#define LANGUAGE "c"
#define BENCHMARK "jit_function_numeric_sum"
#define ARRAY_SIZE 1000000
#define ITERATIONS 50
#define RESULT_FILE "results/jit_function_c_result.json"
#define RUNNER "vscode_terminal_powershell"
#define RUNNER_LABEL "VSCode Terminal / PowerShell"
#define EXPECTED_CHECKSUM 1000000000000LL
#define PATH_BUFFER_SIZE 4096

#ifndef LANGBENCH_OPTIMIZATION_LEVEL
#define LANGBENCH_OPTIMIZATION_LEVEL "none"
#endif

#ifndef LANGBENCH_COMPILE_COMMAND
#define LANGBENCH_COMPILE_COMMAND "unknown"
#endif

typedef struct {
    int iteration;
    double elapsed_ms;
    int64_t checksum;
} IterationResult;

typedef struct {
    int count;
    double average_ms;
    double median_ms;
    double fastest_ms;
    double slowest_ms;
    double first_iteration_ms;
    double average_ms_excluding_first;
} Summary;

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

static const char *compiler_name(void) {
#if defined(__clang__)
    return "clang";
#elif defined(__GNUC__)
    return "gcc";
#elif defined(_MSC_VER)
    return "msvc";
#else
    return "unknown";
#endif
}

static const char *compiler_version(void) {
#if defined(__clang__)
    return __clang_version__;
#elif defined(__GNUC__)
    return __VERSION__;
#elif defined(_MSC_VER)
    static char version_buffer[32];
    snprintf(version_buffer, sizeof(version_buffer), "%d", _MSC_VER);
    return version_buffer;
#else
    return "unknown";
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
    return ((int64_t)(value * 1000.0 + 0.5)) / 1000.0;
}

static double current_time_ms(void) {
#if defined(_WIN32)
    LARGE_INTEGER frequency;
    LARGE_INTEGER counter;

    QueryPerformanceFrequency(&frequency);
    QueryPerformanceCounter(&counter);
    return ((double)counter.QuadPart * 1000.0) / (double)frequency.QuadPart;
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ((double)ts.tv_sec * 1000.0) + ((double)ts.tv_nsec / 1000000.0);
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

static void get_cwd(char *buffer, size_t buffer_size) {
#if defined(_WIN32)
    if (_getcwd(buffer, (int)buffer_size) == NULL) {
        snprintf(buffer, buffer_size, "unknown");
    }
#else
    if (getcwd(buffer, buffer_size) == NULL) {
        snprintf(buffer, buffer_size, "unknown");
    }
#endif
}

static void build_path(char *buffer, size_t buffer_size, const char *left, const char *right) {
    const char separator =
#if defined(_WIN32)
        '\\';
#else
        '/';
#endif
    snprintf(buffer, buffer_size, "%s%c%s", left, separator, right);
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

static long cpu_thread_count(void) {
#if defined(_WIN32)
    SYSTEM_INFO info;
    GetSystemInfo(&info);
    return (long)info.dwNumberOfProcessors;
#else
    long count = sysconf(_SC_NPROCESSORS_ONLN);
    return count > 0 ? count : -1;
#endif
}

static int64_t total_memory_bytes(void) {
#if defined(_WIN32)
    MEMORYSTATUSEX status;
    status.dwLength = sizeof(status);
    if (GlobalMemoryStatusEx(&status) == 0) {
        return -1;
    }
    return (int64_t)status.ullTotalPhys;
#else
    long pages = sysconf(_SC_PHYS_PAGES);
    long page_size = sysconf(_SC_PAGE_SIZE);
    if (pages <= 0 || page_size <= 0) {
        return -1;
    }
    return (int64_t)pages * (int64_t)page_size;
#endif
}

static void cpu_model(char *buffer, size_t buffer_size) {
#if defined(_WIN32)
    HKEY key;
    DWORD value_size = (DWORD)buffer_size;
    LONG status = RegOpenKeyExA(
        HKEY_LOCAL_MACHINE,
        "HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0",
        0,
        KEY_READ,
        &key
    );

    if (status != ERROR_SUCCESS) {
        snprintf(buffer, buffer_size, "unknown");
        return;
    }

    status = RegQueryValueExA(key, "ProcessorNameString", NULL, NULL, (LPBYTE)buffer, &value_size);
    RegCloseKey(key);

    if (status != ERROR_SUCCESS) {
        snprintf(buffer, buffer_size, "unknown");
    }
#else
    snprintf(buffer, buffer_size, "unknown");
#endif
}

static int64_t transform_value(int64_t value) {
    return value * 2 + 1;
}

static int64_t *create_number_array(size_t array_size) {
    size_t index;
    int64_t *values = (int64_t *)malloc(array_size * sizeof(int64_t));

    if (values == NULL) {
        fprintf(stderr, "status=error\n");
        fprintf(stderr, "message=failed to allocate number array\n");
        exit(1);
    }

    for (index = 0; index < array_size; index += 1) {
        values[index] = (int64_t)index;
    }

    return values;
}

static int64_t sum_transformed_array(const int64_t *values, size_t array_size) {
    size_t index;
    int64_t total = 0;

    for (index = 0; index < array_size; index += 1) {
        total += transform_value(values[index]);
    }

    return total;
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

static Summary summarize_results(const IterationResult results[ITERATIONS]) {
    Summary summary;
    double elapsed_values[ITERATIONS];
    double total = 0.0;
    double total_excluding_first = 0.0;
    int i;

    for (i = 0; i < ITERATIONS; i += 1) {
        elapsed_values[i] = results[i].elapsed_ms;
        total += results[i].elapsed_ms;
        if (i > 0) {
            total_excluding_first += results[i].elapsed_ms;
        }
    }

    qsort(elapsed_values, ITERATIONS, sizeof(double), compare_double);

    summary.count = ITERATIONS;
    summary.average_ms = round_ms(total / ITERATIONS);
    summary.median_ms = round_ms(elapsed_values[ITERATIONS / 2]);
    summary.fastest_ms = round_ms(elapsed_values[0]);
    summary.slowest_ms = round_ms(elapsed_values[ITERATIONS - 1]);
    summary.first_iteration_ms = round_ms(results[0].elapsed_ms);
    summary.average_ms_excluding_first = round_ms(total_excluding_first / (ITERATIONS - 1));

    return summary;
}

static const char *status_from_results(const IterationResult results[ITERATIONS]) {
    int i;

    for (i = 0; i < ITERATIONS; i += 1) {
        if (results[i].checksum != EXPECTED_CHECKSUM) {
            return "failed";
        }
    }

    return "success";
}

static void write_results_array(FILE *output, const IterationResult results[ITERATIONS]) {
    int i;

    fprintf(output, "  \"results\": [\n");
    for (i = 0; i < ITERATIONS; i += 1) {
        fprintf(output, "    {\n");
        fprintf(output, "      \"iteration\": %d,\n", results[i].iteration);
        fprintf(output, "      \"elapsed_ms\": %.3f,\n", results[i].elapsed_ms);
        fprintf(output, "      \"checksum\": %lld\n", (long long)results[i].checksum);
        fprintf(output, "    }%s\n", i == ITERATIONS - 1 ? "" : ",");
    }
    fprintf(output, "  ],\n");
}

static void write_result_json(
    const char *output_path,
    const char *status,
    const IterationResult results[ITERATIONS],
    const Summary *summary,
    double setup_ms,
    int argc,
    char *argv[]
) {
    FILE *output = fopen(output_path, "w");
    char created_at[32];
    char cwd[PATH_BUFFER_SIZE];
    char output_file[PATH_BUFFER_SIZE];
    char command[PATH_BUFFER_SIZE];
    char cpu_name[256];
    int64_t memory_bytes = total_memory_bytes();
    int i;

    if (output == NULL) {
        fprintf(stderr, "status=error\n");
        fprintf(stderr, "message=failed to open result file: %s (%s)\n", output_path, strerror(errno));
        exit(1);
    }

    build_timestamp(created_at, sizeof(created_at));
    get_cwd(cwd, sizeof(cwd));
    build_path(output_file, sizeof(output_file), cwd, output_path);
    cpu_model(cpu_name, sizeof(cpu_name));
    command[0] = '\0';
    for (i = 0; i < argc; i += 1) {
        if (i > 0) {
            strncat(command, " ", sizeof(command) - strlen(command) - 1);
        }
        strncat(command, argv[i], sizeof(command) - strlen(command) - 1);
    }

    fprintf(output, "{\n");
    fprintf(output, "  \"type\": \"langbench_result\",\n");
    fprintf(output, "  \"schema_version\": \"%s\",\n", SCHEMA_VERSION);
    fprintf(output, "  \"project\": \"%s\",\n", PROJECT);
    fprintf(output, "  \"benchmark\": \"%s\",\n", BENCHMARK);
    fprintf(output, "  \"experiment\": \"%s\",\n", BENCHMARK);
    fprintf(output, "  \"language\": \"%s\",\n", LANGUAGE);
    fprintf(output, "  \"created_at\": \"%s\",\n", created_at);
    fprintf(output, "  \"status\": \"%s\",\n", status);
    fprintf(output, "  \"engine\": {\n");
    fprintf(output, "    \"runtime\": \"native\",\n");
    fprintf(output, "    \"compiler_name\": \"%s\",\n", compiler_name());
    fprintf(output, "    \"compiler_version\": ");
    write_json_string(output, compiler_version());
    fprintf(output, ",\n");
    fprintf(output, "    \"compile_command\": ");
    write_json_string(output, LANGBENCH_COMPILE_COMMAND);
    fprintf(output, ",\n");
    fprintf(output, "    \"optimization_level\": ");
    write_json_string(output, LANGBENCH_OPTIMIZATION_LEVEL);
    fprintf(output, "\n");
    fprintf(output, "  },\n");
    fprintf(output, "  \"execution\": {\n");
    fprintf(output, "    \"runner\": \"%s\",\n", RUNNER);
    fprintf(output, "    \"runner_label\": \"%s\",\n", RUNNER_LABEL);
    fprintf(output, "    \"cwd\": ");
    write_json_string(output, cwd);
    fprintf(output, ",\n");
    fprintf(output, "    \"argv\": [\n");
    for (i = 0; i < argc; i += 1) {
        fprintf(output, "      ");
        write_json_string(output, argv[i]);
        fprintf(output, "%s\n", i == argc - 1 ? "" : ",");
    }
    fprintf(output, "    ],\n");
    fprintf(output, "    \"command\": ");
    write_json_string(output, command);
    fprintf(output, ",\n");
    fprintf(output, "    \"script_path\": ");
    write_json_string(output, argv[0]);
    fprintf(output, "\n");
    fprintf(output, "  },\n");
    fprintf(output, "  \"runtime\": {\n");
    fprintf(output, "    \"name\": \"c\",\n");
    fprintf(output, "    \"version\": \"%s\"\n", runtime_standard());
    fprintf(output, "  },\n");
    fprintf(output, "  \"environment\": {\n");
    fprintf(output, "    \"os_name\": \"%s\",\n", os_name());
    fprintf(output, "    \"os_platform\": \"%s\",\n", os_platform());
    fprintf(output, "    \"os_version\": \"unknown\",\n");
    fprintf(output, "    \"cpu_model\": ");
    write_json_string(output, cpu_name);
    fprintf(output, ",\n");
    fprintf(output, "    \"cpu_threads\": %ld,\n", cpu_thread_count());
    if (memory_bytes >= 0) {
        fprintf(output, "    \"memory_total_bytes\": %lld\n", (long long)memory_bytes);
    } else {
        fprintf(output, "    \"memory_total_bytes\": null\n");
    }
    fprintf(output, "  },\n");
    fprintf(output, "  \"compilation\": {\n");
    fprintf(output, "    \"compiler_name\": \"%s\",\n", compiler_name());
    fprintf(output, "    \"compiler_version\": ");
    write_json_string(output, compiler_version());
    fprintf(output, ",\n");
    fprintf(output, "    \"compile_command\": ");
    write_json_string(output, LANGBENCH_COMPILE_COMMAND);
    fprintf(output, ",\n");
    fprintf(output, "    \"optimization_level\": ");
    write_json_string(output, LANGBENCH_OPTIMIZATION_LEVEL);
    fprintf(output, "\n");
    fprintf(output, "  },\n");
    fprintf(output, "  \"output_file\": ");
    write_json_string(output, output_file);
    fprintf(output, ",\n");
    fprintf(output, "  \"array_size\": %d,\n", ARRAY_SIZE);
    fprintf(output, "  \"iterations\": %d,\n", ITERATIONS);
    fprintf(output, "  \"setup_ms\": %.3f,\n", setup_ms);
    fprintf(output, "  \"expected_checksum\": %lld,\n", (long long)EXPECTED_CHECKSUM);
    write_results_array(output, results);
    fprintf(output, "  \"summary\": {\n");
    fprintf(output, "    \"count\": %d,\n", summary->count);
    fprintf(output, "    \"average_ms\": %.3f,\n", summary->average_ms);
    fprintf(output, "    \"median_ms\": %.3f,\n", summary->median_ms);
    fprintf(output, "    \"fastest_ms\": %.3f,\n", summary->fastest_ms);
    fprintf(output, "    \"slowest_ms\": %.3f,\n", summary->slowest_ms);
    fprintf(output, "    \"first_iteration_ms\": %.3f,\n", summary->first_iteration_ms);
    fprintf(output, "    \"average_ms_excluding_first\": %.3f\n", summary->average_ms_excluding_first);
    fprintf(output, "  }\n");
    fprintf(output, "}\n");

    if (fclose(output) != 0) {
        fprintf(stderr, "status=error\n");
        fprintf(stderr, "message=failed to close result file: %s\n", output_path);
        exit(1);
    }
}

int main(int argc, char *argv[]) {
    int64_t *values;
    IterationResult results[ITERATIONS];
    Summary summary;
    const char *status;
    double setup_start_ms;
    double setup_end_ms;
    double setup_ms;
    int iteration;

    setup_start_ms = current_time_ms();
    values = create_number_array(ARRAY_SIZE);
    setup_end_ms = current_time_ms();
    setup_ms = round_ms(setup_end_ms - setup_start_ms);

    for (iteration = 0; iteration < ITERATIONS; iteration += 1) {
        double start_ms = current_time_ms();
        int64_t checksum = sum_transformed_array(values, ARRAY_SIZE);
        double end_ms = current_time_ms();

        results[iteration].iteration = iteration + 1;
        results[iteration].elapsed_ms = round_ms(end_ms - start_ms);
        results[iteration].checksum = checksum;
    }

    summary = summarize_results(results);
    status = status_from_results(results);

    write_result_json(RESULT_FILE, status, results, &summary, setup_ms, argc, argv);
    free(values);

    printf("status=%s\n", status);
    return strcmp(status, "success") == 0 ? 0 : 1;
}

#define main langbench_benchmark_main
#include "../benchmarks/function_call_numeric_sum/c/main.c"
#undef main

static LONG WINAPI successful_query(OSVERSIONINFOW *version) {
    if (version->dwOSVersionInfoSize != sizeof(*version)) return 1;
    version->dwMajorVersion = 10;
    version->dwMinorVersion = 0;
    version->dwBuildNumber = 26200;
    return 0;
}

static LONG WINAPI failed_query(OSVERSIONINFOW *version) {
    (void)version;
    return 1;
}

int main(void) {
    char version[64] = "unchanged";
    char tiny[4];
    if (!format_os_version(successful_query, version, sizeof(version)) || strcmp(version, "10.0.26200") != 0) return 1;
    if (format_os_version(failed_query, version, sizeof(version))) return 2;
    if (format_os_version(NULL, version, sizeof(version))) return 3;
    if (format_os_version(successful_query, tiny, sizeof(tiny))) return 4;
    if (!get_os_version(version, sizeof(version))) return 5;
    printf("os_version=%s\n", version);
    return 0;
}

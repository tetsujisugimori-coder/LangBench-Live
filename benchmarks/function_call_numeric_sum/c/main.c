#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif
#define N 1000000
#define W 5
#define I 50
#define E 500000500000LL
static double now_ms(void){LARGE_INTEGER f,c;QueryPerformanceFrequency(&f);QueryPerformanceCounter(&c);return c.QuadPart*1000.0/f.QuadPart;}
static double rnd(double x){return (int64_t)(x*1000+.5)/1000.0;}
static int64_t direct(const int32_t*v){int64_t t=0;int i;for(i=0;i<N;i++)t+=v[i];return t;}
#if defined(_MSC_VER)
#define NOINLINE __declspec(noinline)
#elif defined(__GNUC__) || defined(__clang__)
#define NOINLINE __attribute__((noinline))
#else
#define NOINLINE
#endif
static NOINLINE int64_t add(int64_t a,int32_t b){return a+b;}
static int64_t called(const int32_t*v){int64_t t=0;int i;for(i=0;i<N;i++)t=add(t,v[i]);return t;}
static int cmp(const void*a,const void*b){double x=*(double*)a,y=*(double*)b;return x>y?1:x<y?-1:0;}
static void write_stats(FILE*out,double*s){double x[I],sum=0;int i;for(i=0;i<I;i++){x[i]=s[i];sum+=s[i];}qsort(x,I,sizeof(double),cmp);fprintf(out,"{\n      \"samples_ms\": [");for(i=0;i<I;i++)fprintf(out,"%.3f%s",s[i],i==I-1?"":",");fprintf(out,"],\n      \"min_ms\": %.3f,\n      \"max_ms\": %.3f,\n      \"mean_ms\": %.3f,\n      \"median_ms\": %.3f\n    }",x[0],x[I-1],rnd(sum/I),rnd((x[I/2-1]+x[I/2])/2));}
int main(int argc,char**argv){int32_t*v=malloc(N*sizeof(*v));double ds[I],fs[I],setup,warm=0,measure=0,s;int i;int64_t dc=0,fc=0;char*eid=NULL,*rid=NULL;FILE*out;for(i=0;i<argc;i++){if(!strncmp(argv[i],"--experiment-id=",16))eid=argv[i]+16;if(!strncmp(argv[i],"--run-id=",9))rid=argv[i]+9;}if(!v||!eid||!rid)return 1;s=now_ms();for(i=0;i<N;i++)v[i]=i+1;setup=rnd(now_ms()-s);s=now_ms();for(i=0;i<W;i++)if(direct(v)!=E)return 1;warm+=rnd(now_ms()-s);s=now_ms();for(i=0;i<I;i++){double q=now_ms();dc=direct(v);ds[i]=rnd(now_ms()-q);measure+=ds[i];if(dc!=E)return 1;}s=now_ms();for(i=0;i<W;i++)if(called(v)!=E)return 1;warm+=rnd(now_ms()-s);s=now_ms();for(i=0;i<I;i++){double q=now_ms();fc=called(v);fs[i]=rnd(now_ms()-q);measure+=fs[i];if(fc!=E)return 1;}out=fopen("results/function_call_numeric_sum_c_result.json","w");if(!out)return 1;fprintf(out,"{\n  \"type\": \"langbench_result\",\n  \"schema_version\": \"1.0\",\n  \"project\": \"LangBench Live\",\n  \"benchmark\": \"function_call_numeric_sum\",\n  \"experiment_id\": \"%s\",\n  \"run_id\": \"%s\",\n  \"language\": \"c\",\n  \"created_at\": \"2026-08-21T00:00:00+09:00\",\n  \"status\": \"success\",\n  \"engine\": {\"runtime\":\"native\",\"runtime_version\":null},\n  \"execution\": {\"runner\":\"vscode_terminal_powershell\",\"runner_label\":\"VSCode Terminal / PowerShell\",\"cwd\":null,\"argv\":[]},\n  \"environment\": {\"os\":\"Windows\",\"os_version\":null,\"architecture\":null,\"cpu\":null,\"logical_processors\":null,\"memory_bytes\":null},\n  \"build\": {\"required\":true,\"compiler\":\"gcc\",\"compiler_version\":\"gcc\",\"compile_command\":\"gcc -O2\",\"compile_ms\":0,\"source_path\":\"benchmarks/function_call_numeric_sum/c/main.c\"},\n  \"config\": {\"item_count\":1000000,\"warmup_iterations\":5,\"measurement_iterations\":50,\"numeric_type\":\"integer\",\"value_field\":\"value\",\"cases\":[\"direct\",\"function_call\"]},\n  \"timing\": {\"process_startup_ms\":null,\"setup_ms\":%.3f,\"warmup_ms\":%.3f,\"measurement_ms\":%.3f,\"benchmark_total_ms\":%.3f},\n  \"results\": {\n    \"direct\": ",eid,rid,setup,warm,measure,rnd(setup+warm+measure));write_stats(out,ds);fprintf(out,",\n    \"function_call\": ");write_stats(out,fs);fprintf(out,"\n  },\n  \"validation\": {\"direct_checksum\":%" PRId64 ",\"function_call_checksum\":%" PRId64 ",\"expected_checksum\":%lld,\"tolerance\":0,\"passed\":true},\n  \"error\":null\n}\n",dc,fc,(long long)E);fclose(out);free(v);puts("status=success");return 0;}

	.file	"main.c"
	.intel_syntax noprefix
	.text
	.p2align 4
	.def	"compare_double";	.scl	3;	.type	32;	.endef
	.seh_proc	"compare_double"
"compare_double":
	.seh_endprologue
	xor	eax, eax
	movsd	xmm1, QWORD PTR [rdx]
	movsd	xmm0, QWORD PTR [rcx]
	comisd	xmm0, xmm1
	seta	al
	xor	edx, edx
	comisd	xmm1, xmm0
	seta	dl
	sub	eax, edx
	ret
	.seh_endproc
	.p2align 4
	.def	"direct_sum";	.scl	3;	.type	32;	.endef
	.seh_proc	"direct_sum"
"direct_sum":
	.seh_endprologue
	pxor	xmm1, xmm1
	lea	rax, 4000000[rcx]
	.p2align 6
	.p2align 4
	.p2align 3
.L4:
	movdqu	xmm0, XMMWORD PTR [rcx]
	add	rcx, 16
	movdqa	xmm2, xmm0
	movdqa	xmm3, xmm0
	psrad	xmm2, 31
	punpckldq	xmm3, xmm2
	punpckhdq	xmm0, xmm2
	paddq	xmm1, xmm3
	paddq	xmm1, xmm0
	cmp	rax, rcx
	jne	.L4
	movdqa	xmm0, xmm1
	psrldq	xmm0, 8
	paddq	xmm1, xmm0
	movq	rax, xmm1
	ret
	.seh_endproc
	.p2align 4
	.def	"add";	.scl	3;	.type	32;	.endef
	.seh_proc	"add"
"add":
	.seh_endprologue
	movsxd	rax, edx
	add	rax, rcx
	ret
	.seh_endproc
	.p2align 4
	.def	"function_call_sum";	.scl	3;	.type	32;	.endef
	.seh_proc	"function_call_sum"
"function_call_sum":
	sub	rsp, 40
	.seh_stackalloc	40
	.seh_endprologue
	mov	r8, rcx
	lea	r9, 4000000[rcx]
	xor	ecx, ecx
	.p2align 4
	.p2align 3
.L8:
	mov	edx, DWORD PTR [r8]
	add	r8, 4
	call	"add"
	mov	rcx, rax
	cmp	r8, r9
	jne	.L8
	add	rsp, 40
	ret
	.seh_endproc
	.p2align 4
	.def	"sample_total";	.scl	3;	.type	32;	.endef
	.seh_proc	"sample_total"
"sample_total":
	.seh_endprologue
	pxor	xmm0, xmm0
	lea	rax, 400[rcx]
	.p2align 5
	.p2align 4
	.p2align 3
.L11:
	addsd	xmm0, QWORD PTR [rcx]
	add	rcx, 16
	addsd	xmm0, QWORD PTR -8[rcx]
	cmp	rax, rcx
	jne	.L11
	movsd	xmm1, QWORD PTR .LC1[rip]
	mulsd	xmm0, xmm1
	addsd	xmm0, QWORD PTR .LC2[rip]
	cvttsd2si	rax, xmm0
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, rax
	divsd	xmm0, xmm1
	ret
	.seh_endproc
	.p2align 4
	.def	"now_ms";	.scl	3;	.type	32;	.endef
	.seh_proc	"now_ms"
"now_ms":
	sub	rsp, 56
	.seh_stackalloc	56
	.seh_endprologue
	lea	rcx, 40[rsp]
	call	[QWORD PTR __imp_QueryPerformanceCounter[rip]]
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, QWORD PTR 40[rsp]
	pxor	xmm1, xmm1
	mulsd	xmm0, QWORD PTR .LC1[rip]
	cvtsi2sd	xmm1, QWORD PTR "timer_frequency"[rip]
	divsd	xmm0, xmm1
	add	rsp, 56
	ret
	.seh_endproc
	.section .rdata,"dr"
.LC3:
	.ascii "\\\"\0"
.LC4:
	.ascii "\\\\\0"
.LC5:
	.ascii "\\n\0"
.LC6:
	.ascii "\\r\0"
.LC7:
	.ascii "\\t\0"
.LC8:
	.ascii "\\u%04x\0"
	.text
	.p2align 4
	.def	"write_json_string";	.scl	3;	.type	32;	.endef
	.seh_proc	"write_json_string"
"write_json_string":
	push	rsi
	.seh_pushreg	rsi
	push	rbx
	.seh_pushreg	rbx
	sub	rsp, 40
	.seh_stackalloc	40
	.seh_endprologue
	mov	rbx, rdx
	mov	rsi, rcx
	mov	rdx, rcx
	mov	ecx, 34
	call	"fputc"
	movzx	eax, BYTE PTR [rbx]
	test	al, al
	jne	.L26
	jmp	.L15
	.p2align 4,,10
	.p2align 3
.L32:
	cmp	al, 9
	je	.L18
	movzx	r8d, al
	cmp	al, 10
	jne	.L20
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	lea	rcx, .LC5[rip]
	call	"fwrite"
.L24:
	movzx	eax, BYTE PTR 1[rbx]
	add	rbx, 1
	test	al, al
	je	.L15
.L26:
	cmp	al, 13
	je	.L16
	jbe	.L32
	cmp	al, 34
	je	.L21
	cmp	al, 92
	jne	.L33
	mov	r9, rsi
	mov	edx, 1
	add	rbx, 1
	mov	r8d, 2
	lea	rcx, .LC4[rip]
	call	"fwrite"
	movzx	eax, BYTE PTR [rbx]
	test	al, al
	jne	.L26
.L15:
	mov	rdx, rsi
	mov	ecx, 34
	add	rsp, 40
	pop	rbx
	pop	rsi
	jmp	"fputc"
	.p2align 4,,10
	.p2align 3
.L16:
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	lea	rcx, .LC6[rip]
	call	"fwrite"
	jmp	.L24
	.p2align 4,,10
	.p2align 3
.L18:
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	lea	rcx, .LC7[rip]
	call	"fwrite"
	jmp	.L24
	.p2align 4,,10
	.p2align 3
.L21:
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	lea	rcx, .LC3[rip]
	call	"fwrite"
	jmp	.L24
	.p2align 4,,10
	.p2align 3
.L33:
	movzx	r8d, al
	cmp	al, 31
	jbe	.L20
	mov	rdx, rsi
	mov	ecx, r8d
	call	"fputc"
	jmp	.L24
	.p2align 4,,10
	.p2align 3
.L20:
	lea	rdx, .LC8[rip]
	mov	rcx, rsi
	call	"fprintf"
	jmp	.L24
	.seh_endproc
	.section .rdata,"dr"
.LC9:
	.ascii "{\12      \"samples_ms\": [\0"
.LC10:
	.ascii ",\0"
.LC11:
	.ascii "%.3f%s\0"
	.align 8
.LC12:
	.ascii "],\12      \"min_ms\": %.3f,\12      \"max_ms\": %.3f,\12      \"mean_ms\": %.3f,\12      \"median_ms\": %.3f\12    }\0"
.LC14:
	.ascii "\0"
	.text
	.p2align 4
	.def	"write_case";	.scl	3;	.type	32;	.endef
	.seh_proc	"write_case"
"write_case":
	push	rbp
	.seh_pushreg	rbp
	push	rdi
	.seh_pushreg	rdi
	push	rsi
	.seh_pushreg	rsi
	push	rbx
	.seh_pushreg	rbx
	sub	rsp, 472
	.seh_stackalloc	472
	movups	XMMWORD PTR 448[rsp], xmm6
	.seh_savexmm	xmm6, 448
	.seh_endprologue
	pxor	xmm6, xmm6
	mov	rdi, rcx
	lea	rcx, 48[rsp]
	mov	rsi, rdx
	mov	rbx, rdx
	mov	rax, rcx
	.p2align 6
	.p2align 4
	.p2align 3
.L35:
	movupd	xmm0, XMMWORD PTR [rdx]
	add	rax, 16
	lea	r10, 448[rsp]
	add	rdx, 16
	movapd	xmm1, xmm0
	movups	XMMWORD PTR -16[rax], xmm0
	unpckhpd	xmm0, xmm0
	addsd	xmm1, xmm6
	movapd	xmm6, xmm0
	addsd	xmm6, xmm1
	cmp	r10, rax
	jne	.L35
	lea	r9, "compare_double"[rip]
	mov	r8d, 8
	mov	edx, 50
	call	"qsort"
	mov	r9, rdi
	mov	r8d, 23
	mov	edx, 1
	lea	rcx, .LC9[rip]
	lea	rbp, 392[rsi]
	add	rsi, 400
	call	"fwrite"
	jmp	.L37
	.p2align 4,,10
	.p2align 3
.L42:
	lea	r9, .LC10[rip]
	movq	xmm2, r8
	mov	rcx, rdi
	add	rbx, 8
	lea	rdx, .LC11[rip]
	call	"fprintf"
	cmp	rbx, rsi
	je	.L38
.L37:
	mov	r8, QWORD PTR [rbx]
	cmp	rbp, rbx
	jne	.L42
	lea	r9, .LC14[rip]
	movq	xmm2, r8
	lea	rdx, .LC11[rip]
	mov	rcx, rdi
	call	"fprintf"
.L38:
	movsd	xmm0, QWORD PTR 240[rsp]
	movsd	xmm2, QWORD PTR .LC2[rip]
	divsd	xmm6, QWORD PTR .LC13[rip]
	lea	rdx, .LC12[rip]
	addsd	xmm0, QWORD PTR 248[rsp]
	movsd	xmm1, QWORD PTR .LC1[rip]
	mov	rcx, rdi
	movsd	xmm3, QWORD PTR 440[rsp]
	mulsd	xmm6, xmm1
	mulsd	xmm0, xmm2
	movq	r9, xmm3
	addsd	xmm6, xmm2
	mulsd	xmm0, xmm1
	addsd	xmm0, xmm2
	movsd	xmm2, QWORD PTR 48[rsp]
	movq	r8, xmm2
	cvttsd2si	rax, xmm0
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, rax
	divsd	xmm0, xmm1
	cvttsd2si	rax, xmm6
	movsd	QWORD PTR 40[rsp], xmm0
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, rax
	divsd	xmm0, xmm1
	movsd	QWORD PTR 32[rsp], xmm0
	call	"fprintf"
	nop
	movups	xmm6, XMMWORD PTR 448[rsp]
	add	rsp, 472
	pop	rbx
	pop	rsi
	pop	rdi
	pop	rbp
	ret
	.seh_endproc
	.p2align 4
	.def	"optional_arg.constprop.0";	.scl	3;	.type	32;	.endef
	.seh_proc	"optional_arg.constprop.0"
"optional_arg.constprop.0":
	push	r13
	.seh_pushreg	r13
	push	r12
	.seh_pushreg	r12
	push	rbp
	.seh_pushreg	rbp
	push	rdi
	.seh_pushreg	rdi
	push	rsi
	.seh_pushreg	rsi
	push	rbx
	.seh_pushreg	rbx
	sub	rsp, 40
	.seh_stackalloc	40
	.seh_endprologue
	mov	esi, ecx
	mov	r12, rdx
	mov	rdi, r8
	mov	r13, r9
	cmp	ecx, 5
	jle	.L48
	mov	rcx, r8
	lea	rbx, 40[r12]
	call	"strlen"
	mov	rbp, rax
	lea	eax, -6[rsi]
	lea	r12, 48[r12+rax*8]
	jmp	.L47
	.p2align 4,,10
	.p2align 3
.L46:
	add	rbx, 8
	cmp	rbx, r12
	je	.L48
.L47:
	mov	rsi, QWORD PTR [rbx]
	mov	r8, rbp
	mov	rdx, rdi
	mov	rcx, rsi
	call	"strncmp"
	test	eax, eax
	jne	.L46
	lea	rdx, [rsi+rbp]
	mov	r8d, 255
	mov	rcx, r13
	call	"strncpy"
	mov	BYTE PTR 255[r13], 0
	mov	eax, 1
	jmp	.L43
.L48:
	xor	eax, eax
.L43:
	add	rsp, 40
	pop	rbx
	pop	rsi
	pop	rdi
	pop	rbp
	pop	r12
	pop	r13
	ret
	.seh_endproc
	.section .rdata,"dr"
.LC15:
	.ascii "%04u%02u%02u_%02u%02u%02u\0"
	.text
	.p2align 4
	.def	"timestamp_id.constprop.0";	.scl	3;	.type	32;	.endef
	.seh_proc	"timestamp_id.constprop.0"
"timestamp_id.constprop.0":
	push	rbx
	.seh_pushreg	rbx
	sub	rsp, 96
	.seh_stackalloc	96
	.seh_endprologue
	mov	rbx, rcx
	lea	rcx, 80[rsp]
	call	[QWORD PTR __imp_GetLocalTime[rip]]
	movzx	eax, WORD PTR 92[rsp]
	movzx	r9d, WORD PTR 80[rsp]
	mov	rcx, rbx
	lea	r8, .LC15[rip]
	mov	edx, 64
	mov	DWORD PTR 64[rsp], eax
	movzx	eax, WORD PTR 90[rsp]
	mov	DWORD PTR 56[rsp], eax
	movzx	eax, WORD PTR 88[rsp]
	mov	DWORD PTR 48[rsp], eax
	movzx	eax, WORD PTR 86[rsp]
	mov	DWORD PTR 40[rsp], eax
	movzx	eax, WORD PTR 82[rsp]
	mov	DWORD PTR 32[rsp], eax
	call	"snprintf"
	nop
	add	rsp, 96
	pop	rbx
	ret
	.seh_endproc
	.p2align 4
	.def	"measure.constprop.0";	.scl	3;	.type	32;	.endef
	.seh_proc	"measure.constprop.0"
"measure.constprop.0":
	push	r15
	.seh_pushreg	r15
	push	r14
	.seh_pushreg	r14
	push	r13
	.seh_pushreg	r13
	push	r12
	.seh_pushreg	r12
	push	rbp
	.seh_pushreg	rbp
	push	rdi
	.seh_pushreg	rdi
	push	rsi
	.seh_pushreg	rsi
	push	rbx
	.seh_pushreg	rbx
	sub	rsp, 120
	.seh_stackalloc	120
	movups	XMMWORD PTR 64[rsp], xmm6
	.seh_savexmm	xmm6, 64
	movups	XMMWORD PTR 80[rsp], xmm7
	.seh_savexmm	xmm7, 80
	movups	XMMWORD PTR 96[rsp], xmm8
	.seh_savexmm	xmm8, 96
	.seh_endprologue
	mov	rbx, QWORD PTR __imp_QueryPerformanceCounter[rip]
	mov	r12d, 5
	movabs	r13, 500000500000
	mov	rsi, QWORD PTR 224[rsp]
	mov	QWORD PTR 208[rsp], r8
	mov	rdi, rcx
	mov	rbp, rdx
	mov	r14, r9
	lea	rcx, 56[rsp]
	call	rbx
	mov	rax, QWORD PTR "timer_frequency"[rip]
	mov	r15, QWORD PTR 56[rsp]
	mov	QWORD PTR 40[rsp], rax
.L54:
	mov	rcx, rdi
	call	rbp
	cmp	rax, r13
	jne	.L55
	sub	r12d, 1
	jne	.L54
	movsd	xmm7, QWORD PTR .LC1[rip]
	pxor	xmm6, xmm6
	pxor	xmm0, xmm0
	lea	rcx, 56[rsp]
	cvtsi2sd	xmm6, r15
	cvtsi2sd	xmm0, QWORD PTR 40[rsp]
	lea	r13, 400[r14]
	movabs	r12, 500000500000
	mulsd	xmm6, xmm7
	divsd	xmm6, xmm0
	call	rbx
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, QWORD PTR 56[rsp]
	pxor	xmm1, xmm1
	cvtsi2sd	xmm1, QWORD PTR "timer_frequency"[rip]
	mulsd	xmm0, xmm7
	movsd	xmm8, QWORD PTR .LC2[rip]
	divsd	xmm0, xmm1
	subsd	xmm0, xmm6
	mulsd	xmm0, xmm7
	addsd	xmm0, xmm8
	cvttsd2si	rax, xmm0
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, rax
	divsd	xmm0, xmm7
	mov	rax, QWORD PTR 208[rsp]
	movsd	QWORD PTR [rax], xmm0
	jmp	.L56
	.p2align 4,,10
	.p2align 3
.L60:
	add	r14, 8
	cmp	r13, r14
	je	.L59
.L56:
	lea	rcx, 56[rsp]
	pxor	xmm6, xmm6
	call	rbx
	cvtsi2sd	xmm6, QWORD PTR 56[rsp]
	mulsd	xmm6, xmm7
	mov	rcx, rdi
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, QWORD PTR "timer_frequency"[rip]
	divsd	xmm6, xmm0
	call	rbp
	lea	rcx, 56[rsp]
	mov	QWORD PTR [rsi], rax
	call	rbx
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, QWORD PTR 56[rsp]
	pxor	xmm1, xmm1
	cvtsi2sd	xmm1, QWORD PTR "timer_frequency"[rip]
	mulsd	xmm0, xmm7
	divsd	xmm0, xmm1
	subsd	xmm0, xmm6
	mulsd	xmm0, xmm7
	addsd	xmm0, xmm8
	cvttsd2si	rax, xmm0
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, rax
	divsd	xmm0, xmm7
	movsd	QWORD PTR [r14], xmm0
	cmp	QWORD PTR [rsi], r12
	je	.L60
.L55:
	xor	eax, eax
.L51:
	movups	xmm6, XMMWORD PTR 64[rsp]
	movups	xmm7, XMMWORD PTR 80[rsp]
	movups	xmm8, XMMWORD PTR 96[rsp]
	add	rsp, 120
	pop	rbx
	pop	rsi
	pop	rdi
	pop	rbp
	pop	r12
	pop	r13
	pop	r14
	pop	r15
	ret
.L59:
	mov	eax, 1
	jmp	.L51
	.seh_endproc
	.section .rdata,"dr"
.LC17:
	.ascii "x64\0"
.LC18:
	.ascii "arm\0"
.LC19:
	.ascii "x86\0"
.LC20:
	.ascii "arm64\0"
.LC21:
	.ascii "%lf\0"
	.align 8
.LC22:
	.ascii "status=error\12message=expected build and optimization analysis arguments\12\0"
	.align 8
.LC23:
	.ascii "status=error\12message=high-resolution timer is unavailable\12\0"
.LC24:
	.ascii "--experiment-id=\0"
.LC25:
	.ascii "LANGBENCH_EXPERIMENT_ID\0"
.LC26:
	.ascii "--run-id=\0"
.LC27:
	.ascii "LANGBENCH_RUN_ID\0"
.LC28:
	.ascii "%s_%s\0"
.LC29:
	.ascii "function_call_numeric_sum\0"
.LC30:
	.ascii "%s_%s_%s\0"
.LC31:
	.ascii "c\0"
	.align 8
.LC32:
	.ascii "status=error\12message=failed to allocate array\12\0"
	.align 8
.LC36:
	.ascii "status=error\12message=checksum mismatch\12\0"
	.align 8
.LC37:
	.ascii "status=error\12message=failed to get cwd\12\0"
	.align 8
.LC38:
	.ascii "status=error\12message=result path is too long\12\0"
	.align 8
.LC39:
	.ascii "results\\function_call_numeric_sum_c_result.json\0"
.LC40:
	.ascii "%Y-%m-%dT%H:%M:%S\0"
.LC41:
	.ascii "%s%c%02d:%02d\0"
	.align 8
.LC42:
	.ascii "HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0\0"
.LC43:
	.ascii "ProcessorNameString\0"
.LC44:
	.ascii "wb\0"
	.align 8
.LC45:
	.ascii "status=error\12message=failed to open result: %s\12\0"
	.align 8
.LC46:
	.ascii "{\12  \"type\": \"langbench_result\",\12  \"schema_version\": \"1.0\",\12  \"project\": \"LangBench Live\",\12  \"benchmark\": \"%s\",\12  \"experiment_id\": \0"
.LC47:
	.ascii ",\12  \"run_id\": \0"
	.align 8
.LC48:
	.ascii ",\12  \"language\": \"c\",\12  \"created_at\": \0"
	.align 8
.LC49:
	.ascii ",\12  \"status\": \"success\",\12  \"engine\": {\"runtime\": \"native\", \"runtime_version\": null},\12  \"execution\": {\"runner\": \"vscode_terminal_powershell\", \"runner_label\": \"VSCode Terminal / PowerShell\", \"cwd\": \0"
.LC50:
	.ascii ", \"argv\": [\0"
.LC51:
	.ascii ", \0"
	.align 8
.LC52:
	.ascii "]},\12  \"environment\": {\"os\": \"Windows\", \"os_version\": null, \"architecture\": \0"
.LC53:
	.ascii "null\0"
.LC54:
	.ascii ", \"cpu\": \0"
	.align 8
.LC55:
	.ascii ", \"logical_processors\": %lu, \"memory_bytes\": \0"
.LC56:
	.ascii "%llu\0"
	.align 8
.LC57:
	.ascii "},\12  \"build\": {\"required\": true, \"compiler\": \"gcc\", \"compiler_version\": \0"
.LC58:
	.ascii ", \"compile_command\": \0"
	.align 8
.LC59:
	.ascii ", \"compile_ms\": %.3f, \"source_path\": \0"
	.align 8
.LC60:
	.ascii "},\12  \"optimization_analysis\": \0"
.LC61:
	.ascii "rb\0"
.LC62:
	.ascii ",\12\0"
	.align 8
.LC63:
	.ascii "  \"config\": {\"item_count\": %d, \"warmup_iterations\": %d, \"measurement_iterations\": %d, \"numeric_type\": \"integer\", \"value_field\": \"value\", \"cases\": [\"direct\", \"function_call\"]},\12  \"timing\": {\"process_startup_ms\": null, \"setup_ms\": %.3f, \"warmup_ms\": %.3f, \"measurement_ms\": %.3f, \"benchmark_total_ms\": %.3f},\12  \"results\": {\"direct\": \0"
.LC64:
	.ascii ", \"function_call\": \0"
	.align 8
.LC65:
	.ascii "},\12  \"validation\": {\"direct_checksum\": %lld, \"function_call_checksum\": %lld, \"expected_checksum\": %lld, \"tolerance\": 0, \"passed\": true},\12  \"error\": null\12}\12\0"
	.align 8
.LC66:
	.ascii "status=error\12message=failed to read optimization analysis JSON\12\0"
	.align 8
.LC67:
	.ascii "status=error\12message=failed to finish writing result JSON\12\0"
.LC68:
	.ascii "status=success\0"
	.section	.text.startup,"x"
	.p2align 4
	.globl	"main"
	.def	"main";	.scl	2;	.type	32;	.endef
	.seh_proc	"main"
"main":
	push	r15
	.seh_pushreg	r15
	mov	eax, 14232
	push	r14
	.seh_pushreg	r14
	push	rbp
	.seh_pushreg	rbp
	push	rdi
	.seh_pushreg	rdi
	push	rsi
	.seh_pushreg	rsi
	push	rbx
	.seh_pushreg	rbx
	call	___chkstk_ms
	sub	rsp, rax
	.seh_stackalloc	14232
	movups	XMMWORD PTR 14160[rsp], xmm6
	.seh_savexmm	xmm6, 14160
	movups	XMMWORD PTR 14176[rsp], xmm7
	.seh_savexmm	xmm7, 14176
	movups	XMMWORD PTR 14192[rsp], xmm8
	.seh_savexmm	xmm8, 14192
	movups	XMMWORD PTR 14208[rsp], xmm9
	.seh_savexmm	xmm9, 14208
	.seh_endprologue
	mov	ebx, ecx
	mov	rbp, rdx
	call	"__main"
	pxor	xmm0, xmm0
	mov	QWORD PTR 120[rsp], 0
	mov	QWORD PTR 128[rsp], 0
	movups	XMMWORD PTR 304[rsp], xmm0
	movups	XMMWORD PTR 320[rsp], xmm0
	movups	XMMWORD PTR 336[rsp], xmm0
	movups	XMMWORD PTR 352[rsp], xmm0
	movups	XMMWORD PTR 368[rsp], xmm0
	movups	XMMWORD PTR 384[rsp], xmm0
	movups	XMMWORD PTR 400[rsp], xmm0
	movups	XMMWORD PTR 416[rsp], xmm0
	movups	XMMWORD PTR 432[rsp], xmm0
	movups	XMMWORD PTR 448[rsp], xmm0
	movups	XMMWORD PTR 464[rsp], xmm0
	movups	XMMWORD PTR 480[rsp], xmm0
	movups	XMMWORD PTR 496[rsp], xmm0
	movups	XMMWORD PTR 512[rsp], xmm0
	movups	XMMWORD PTR 528[rsp], xmm0
	movups	XMMWORD PTR 544[rsp], xmm0
	movups	XMMWORD PTR 560[rsp], xmm0
	movups	XMMWORD PTR 576[rsp], xmm0
	movups	XMMWORD PTR 592[rsp], xmm0
	movups	XMMWORD PTR 608[rsp], xmm0
	movups	XMMWORD PTR 624[rsp], xmm0
	movups	XMMWORD PTR 640[rsp], xmm0
	movups	XMMWORD PTR 656[rsp], xmm0
	movups	XMMWORD PTR 672[rsp], xmm0
	movups	XMMWORD PTR 688[rsp], xmm0
	movups	XMMWORD PTR 704[rsp], xmm0
	movups	XMMWORD PTR 720[rsp], xmm0
	movups	XMMWORD PTR 736[rsp], xmm0
	movups	XMMWORD PTR 752[rsp], xmm0
	movups	XMMWORD PTR 768[rsp], xmm0
	movups	XMMWORD PTR 784[rsp], xmm0
	movups	XMMWORD PTR 800[rsp], xmm0
	movups	XMMWORD PTR 816[rsp], xmm0
	movups	XMMWORD PTR 832[rsp], xmm0
	movups	XMMWORD PTR 848[rsp], xmm0
	movups	XMMWORD PTR 864[rsp], xmm0
	movups	XMMWORD PTR 880[rsp], xmm0
	movups	XMMWORD PTR 896[rsp], xmm0
	movups	XMMWORD PTR 912[rsp], xmm0
	movups	XMMWORD PTR 928[rsp], xmm0
	movups	XMMWORD PTR 944[rsp], xmm0
	movups	XMMWORD PTR 960[rsp], xmm0
	movups	XMMWORD PTR 976[rsp], xmm0
	movups	XMMWORD PTR 992[rsp], xmm0
	movups	XMMWORD PTR 1008[rsp], xmm0
	movups	XMMWORD PTR 1024[rsp], xmm0
	movups	XMMWORD PTR 1040[rsp], xmm0
	movups	XMMWORD PTR 1056[rsp], xmm0
	cmp	ebx, 5
	jle	.L62
	mov	rcx, QWORD PTR 8[rbp]
	lea	r8, 96[rsp]
	lea	rdx, .LC21[rip]
	call	"sscanf"
	mov	r10d, eax
	cmp	eax, 1
	je	.L128
.L62:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 72
	mov	edx, 1
	lea	rcx, .LC22[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, 1
.L61:
	movups	xmm6, XMMWORD PTR 14160[rsp]
	mov	eax, r10d
	movups	xmm7, XMMWORD PTR 14176[rsp]
	movups	xmm8, XMMWORD PTR 14192[rsp]
	movups	xmm9, XMMWORD PTR 14208[rsp]
	add	rsp, 14232
	pop	rbx
	pop	rsi
	pop	rdi
	pop	rbp
	pop	r14
	pop	r15
	ret
.L128:
	pxor	xmm0, xmm0
	comisd	xmm0, QWORD PTR 96[rsp]
	ja	.L62
	mov	rax, QWORD PTR 16[rbp]
	cmp	BYTE PTR [rax], 0
	je	.L62
	mov	rax, QWORD PTR 24[rbp]
	cmp	BYTE PTR [rax], 0
	je	.L62
	mov	rax, QWORD PTR 32[rbp]
	cmp	BYTE PTR [rax], 0
	je	.L62
	mov	rax, QWORD PTR 40[rbp]
	cmp	BYTE PTR [rax], 0
	je	.L62
	mov	DWORD PTR 80[rsp], r10d
	lea	rcx, "timer_frequency"[rip]
	call	[QWORD PTR __imp_QueryPerformanceFrequency[rip]]
	mov	r10d, DWORD PTR 80[rsp]
	test	eax, eax
	je	.L65
	cmp	QWORD PTR "timer_frequency"[rip], 0
	je	.L65
	lea	r9, 304[rsp]
	lea	r8, .LC24[rip]
	mov	rdx, rbp
	mov	ecx, ebx
	mov	DWORD PTR 80[rsp], r10d
	call	"optional_arg.constprop.0"
	mov	r10d, DWORD PTR 80[rsp]
	test	eax, eax
	je	.L129
.L67:
	lea	r9, 560[rsp]
	lea	r8, .LC26[rip]
	mov	rdx, rbp
	mov	ecx, ebx
	mov	DWORD PTR 80[rsp], r10d
	call	"optional_arg.constprop.0"
	mov	r10d, DWORD PTR 80[rsp]
	test	eax, eax
	je	.L130
.L68:
	cmp	BYTE PTR 304[rsp], 0
	je	.L131
.L69:
	cmp	BYTE PTR 560[rsp], 0
	je	.L132
.L70:
	mov	DWORD PTR 80[rsp], r10d
	call	"now_ms"
	mov	ecx, 4000000
	movapd	xmm6, xmm0
	call	"malloc"
	mov	r10d, DWORD PTR 80[rsp]
	test	rax, rax
	mov	r14, rax
	je	.L133
	movdqu	xmm0, XMMWORD PTR .LC16[rip]
	movdqu	xmm5, XMMWORD PTR .LC33[rip]
	lea	rdx, 4000000[rax]
	movdqu	xmm4, XMMWORD PTR .LC34[rip]
	movdqu	xmm3, XMMWORD PTR .LC35[rip]
	.p2align 6
	.p2align 4
	.p2align 3
.L73:
	movdqa	xmm2, xmm0
	movdqa	xmm1, xmm0
	paddq	xmm0, xmm3
	add	rax, 16
	paddq	xmm2, xmm5
	shufps	xmm1, xmm2, 136
	paddd	xmm1, xmm4
	movups	XMMWORD PTR -16[rax], xmm1
	cmp	rax, rdx
	jne	.L73
	mov	DWORD PTR 80[rsp], r10d
	call	"now_ms"
	lea	rax, 120[rsp]
	mov	rcx, r14
	lea	r9, 1072[rsp]
	mov	QWORD PTR 32[rsp], rax
	lea	r8, 104[rsp]
	lea	rdx, "direct_sum"[rip]
	movapd	xmm7, xmm0
	call	"measure.constprop.0"
	mov	r10d, DWORD PTR 80[rsp]
	test	eax, eax
	je	.L74
	lea	rax, 128[rsp]
	lea	r8, 112[rsp]
	mov	rcx, r14
	mov	QWORD PTR 32[rsp], rax
	lea	r9, 1472[rsp]
	lea	rdx, "function_call_sum"[rip]
	call	"measure.constprop.0"
	mov	r10d, DWORD PTR 80[rsp]
	test	eax, eax
	mov	r15d, eax
	je	.L74
	lea	rcx, 1072[rsp]
	lea	rdx, 1872[rsp]
	call	"sample_total"
	lea	rcx, 1472[rsp]
	movapd	xmm8, xmm0
	call	"sample_total"
	mov	ecx, 4096
	movapd	xmm9, xmm0
	call	[QWORD PTR __imp_GetCurrentDirectoryA[rip]]
	test	eax, eax
	je	.L134
	lea	rcx, 1872[rsp]
	call	"strlen"
	mov	r8, rax
	lea	rax, 49[rax]
	cmp	rax, 4096
	ja	.L135
	lea	rdx, 1872[rsp]
	lea	rcx, 5968[rsp]
	mov	QWORD PTR 80[rsp], r8
	call	"memcpy"
	mov	r8, QWORD PTR 80[rsp]
	mov	ecx, DWORD PTR .LC39[rip+44]
	lea	rsi, .LC39[rip]
	mov	DWORD PTR 6013[rsp+r8], ecx
	lea	rdi, 5969[rsp+r8]
	mov	ecx, 11
	mov	BYTE PTR 5968[rsp+r8], 92
	rep movsd
	call	_time64
	lea	rdx, 136[rsp]
	lea	rcx, 240[rsp]
	mov	QWORD PTR 136[rsp], rax
	call	_localtime64_s
	lea	r9, 240[rsp]
	lea	r8, .LC40[rip]
	mov	edx, 32
	lea	rcx, 192[rsp]
	call	"strftime"
	lea	rcx, 10064[rsp]
	call	[QWORD PTR __imp_GetTimeZoneInformation[rip]]
	mov	ecx, DWORD PTR 10064[rsp]
	cmp	eax, 1
	je	.L136
	mov	edx, ecx
	add	ecx, DWORD PTR 10232[rsp]
	cmp	eax, 2
	cmovne	ecx, edx
.L80:
	mov	eax, ecx
	lea	r9, 192[rsp]
	mov	r8d, 60
	neg	eax
	cmovs	eax, ecx
	cdq
	idiv	r8d
	test	ecx, ecx
	lea	r8, .LC41[rip]
	setg	cl
	movzx	ecx, cl
	lea	ecx, 43[rcx+rcx]
	mov	DWORD PTR 32[rsp], ecx
	lea	rcx, 144[rsp]
	mov	DWORD PTR 48[rsp], edx
	mov	edx, 48
	mov	DWORD PTR 40[rsp], eax
	call	"snprintf"
	xor	edx, edx
	xor	ecx, ecx
	xor	r8d, r8d
	lea	rax, 10064[rsp]
	mov	QWORD PTR 10064[rsp], rdx
	mov	r9d, 131097
	lea	rdx, .LC42[rip]
	mov	DWORD PTR 240[rsp], ecx
	mov	rcx, -2147483646
	mov	DWORD PTR 136[rsp], 256
	mov	BYTE PTR 816[rsp], 0
	mov	QWORD PTR 32[rsp], rax
	call	[QWORD PTR __imp_RegOpenKeyExA[rip]]
	test	eax, eax
	je	.L137
.L82:
	lea	rcx, 192[rsp]
	call	[QWORD PTR __imp_GetNativeSystemInfo[rip]]
	lea	rcx, 240[rsp]
	mov	DWORD PTR 240[rsp], 64
	call	[QWORD PTR __imp_GlobalMemoryStatusEx[rip]]
	test	eax, eax
	jne	.L83
	xor	eax, eax
	mov	QWORD PTR 248[rsp], rax
.L83:
	lea	rdx, .LC44[rip]
	lea	rcx, 5968[rsp]
	call	"fopen"
	mov	rsi, rax
	test	rax, rax
	je	.L138
	lea	r8, .LC29[rip]
	lea	rdx, .LC46[rip]
	mov	rcx, rax
	call	"fprintf"
	lea	rdx, 304[rsp]
	mov	rcx, rsi
	lea	edi, -1[rbx]
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 14
	mov	edx, 1
	lea	rcx, .LC47[rip]
	call	"fwrite"
	lea	rdx, 560[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 37
	mov	edx, 1
	lea	rcx, .LC48[rip]
	call	"fwrite"
	lea	rdx, 144[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 196
	mov	edx, 1
	lea	rcx, .LC49[rip]
	call	"fwrite"
	lea	rdx, 1872[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 11
	mov	edx, 1
	lea	rcx, .LC50[rip]
	call	"fwrite"
	xor	r10d, r10d
	jmp	.L86
.L139:
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	lea	rcx, .LC51[rip]
	call	"fwrite"
	mov	r10, QWORD PTR 80[rsp]
	add	r10, 1
	cmp	ebx, r10d
	jle	.L85
.L86:
	mov	rdx, QWORD PTR 0[rbp+r10*8]
	mov	rcx, rsi
	mov	QWORD PTR 80[rsp], r10
	call	"write_json_string"
	cmp	rdi, QWORD PTR 80[rsp]
	jne	.L139
.L85:
	mov	r9, rsi
	mov	r8d, 75
	mov	edx, 1
	lea	rcx, .LC52[rip]
	call	"fwrite"
	movzx	eax, WORD PTR 192[rsp]
	cmp	ax, 9
	je	.L102
	ja	.L88
	test	ax, ax
	je	.L103
	lea	rdx, .LC18[rip]
	cmp	ax, 5
	jne	.L89
.L87:
	mov	rcx, rsi
	call	"write_json_string"
.L90:
	mov	r9, rsi
	mov	r8d, 9
	mov	edx, 1
	lea	rcx, .LC54[rip]
	call	"fwrite"
	cmp	BYTE PTR 816[rsp], 0
	je	.L91
	lea	rdx, 816[rsp]
	mov	rcx, rsi
	call	"write_json_string"
.L92:
	mov	r8d, DWORD PTR 224[rsp]
	lea	rdx, .LC55[rip]
	mov	rcx, rsi
	call	"fprintf"
	mov	r8, QWORD PTR 248[rsp]
	test	r8, r8
	je	.L93
	lea	rdx, .LC56[rip]
	mov	rcx, rsi
	call	"fprintf"
.L94:
	mov	r9, rsi
	mov	r8d, 72
	mov	edx, 1
	lea	rcx, .LC57[rip]
	call	"fwrite"
	mov	rdx, QWORD PTR 16[rbp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 21
	mov	edx, 1
	lea	rcx, .LC58[rip]
	call	"fwrite"
	mov	rdx, QWORD PTR 24[rbp]
	mov	rcx, rsi
	call	"write_json_string"
	movsd	xmm2, QWORD PTR 96[rsp]
	lea	rdx, .LC59[rip]
	mov	rcx, rsi
	movq	r8, xmm2
	call	"fprintf"
	mov	rdx, QWORD PTR 32[rbp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 30
	mov	edx, 1
	lea	rcx, .LC60[rip]
	call	"fwrite"
	mov	rcx, QWORD PTR 40[rbp]
	lea	rdx, .LC61[rip]
	call	"fopen"
	mov	rbp, rax
	test	rax, rax
	jne	.L96
	jmp	.L95
.L97:
	mov	r9, rsi
	mov	r8, rbx
	mov	edx, 1
	lea	rcx, 10064[rsp]
	call	"fwrite"
	cmp	rbx, rax
	jne	.L127
.L96:
	mov	r9, rbp
	mov	r8d, 4096
	mov	edx, 1
	lea	rcx, 10064[rsp]
	call	"fread"
	mov	rbx, rax
	test	rax, rax
	jne	.L97
	mov	rcx, rbp
	call	"ferror"
	test	eax, eax
	jne	.L127
	movapd	xmm0, xmm7
	pxor	xmm4, xmm4
	pxor	xmm5, xmm5
	mov	rcx, rbp
	subsd	xmm0, xmm6
	movsd	xmm1, QWORD PTR .LC1[rip]
	mulsd	xmm0, xmm1
	addsd	xmm0, QWORD PTR .LC2[rip]
	cvttsd2si	rax, xmm0
	movapd	xmm0, xmm8
	addsd	xmm0, xmm9
	mulsd	xmm0, xmm1
	cvtsi2sd	xmm4, rax
	addsd	xmm0, QWORD PTR .LC2[rip]
	divsd	xmm4, xmm1
	cvttsd2si	rax, xmm0
	cvtsi2sd	xmm5, rax
	divsd	xmm5, xmm1
	movsd	QWORD PTR 88[rsp], xmm4
	movsd	QWORD PTR 80[rsp], xmm5
	call	"fclose"
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	lea	rcx, .LC62[rip]
	call	"fwrite"
	movsd	xmm2, QWORD PTR 104[rsp]
	mov	rcx, rsi
	movsd	xmm4, QWORD PTR 88[rsp]
	movsd	xmm3, QWORD PTR 112[rsp]
	movsd	xmm5, QWORD PTR 80[rsp]
	mov	DWORD PTR 32[rsp], 50
	mov	r9d, 5
	movapd	xmm0, xmm2
	movsd	xmm1, QWORD PTR .LC1[rip]
	movsd	QWORD PTR 40[rsp], xmm4
	mov	r8d, 1000000
	addsd	xmm0, xmm4
	addsd	xmm2, xmm3
	movsd	QWORD PTR 56[rsp], xmm5
	lea	rdx, .LC63[rip]
	addsd	xmm0, xmm3
	mulsd	xmm2, xmm1
	addsd	xmm2, QWORD PTR .LC2[rip]
	addsd	xmm0, xmm5
	mulsd	xmm0, xmm1
	addsd	xmm0, QWORD PTR .LC2[rip]
	cvttsd2si	rax, xmm0
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, rax
	divsd	xmm0, xmm1
	cvttsd2si	rax, xmm2
	movsd	QWORD PTR 64[rsp], xmm0
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, rax
	divsd	xmm0, xmm1
	movsd	QWORD PTR 48[rsp], xmm0
	call	"fprintf"
	lea	rdx, 1072[rsp]
	mov	rcx, rsi
	call	"write_case"
	mov	r9, rsi
	mov	r8d, 19
	mov	edx, 1
	lea	rcx, .LC64[rip]
	call	"fwrite"
	lea	rdx, 1472[rsp]
	mov	rcx, rsi
	call	"write_case"
	mov	r9, QWORD PTR 128[rsp]
	mov	r8, QWORD PTR 120[rsp]
	mov	rcx, rsi
	movabs	rax, 500000500000
	lea	rdx, .LC65[rip]
	mov	QWORD PTR 32[rsp], rax
	call	"fprintf"
	mov	rcx, rsi
	call	"ferror"
	mov	rcx, rsi
	mov	ebx, eax
	call	"fclose"
	or	eax, ebx
	je	.L140
	mov	rcx, r14
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 58
	mov	edx, 1
	lea	rcx, .LC67[rip]
	mov	r9, rax
	call	"fwrite"
.L77:
	mov	r10d, r15d
	jmp	.L61
.L65:
	mov	DWORD PTR 80[rsp], r10d
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 58
	mov	edx, 1
	lea	rcx, .LC23[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 80[rsp]
	jmp	.L61
.L74:
	mov	rcx, r14
	mov	DWORD PTR 80[rsp], r10d
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 39
	mov	edx, 1
	lea	rcx, .LC36[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 80[rsp]
	jmp	.L61
.L132:
	lea	rcx, 10064[rsp]
	mov	DWORD PTR 80[rsp], r10d
	call	"timestamp_id.constprop.0"
	lea	rax, .LC29[rip]
	mov	edx, 256
	lea	r9, 10064[rsp]
	mov	QWORD PTR 40[rsp], rax
	lea	rax, .LC31[rip]
	lea	r8, .LC30[rip]
	mov	QWORD PTR 32[rsp], rax
	lea	rcx, 560[rsp]
	call	"snprintf"
	mov	r10d, DWORD PTR 80[rsp]
	jmp	.L70
.L131:
	lea	rcx, 10064[rsp]
	mov	DWORD PTR 80[rsp], r10d
	call	"timestamp_id.constprop.0"
	lea	rax, .LC29[rip]
	mov	edx, 256
	lea	r9, 10064[rsp]
	mov	QWORD PTR 32[rsp], rax
	lea	r8, .LC28[rip]
	lea	rcx, 304[rsp]
	call	"snprintf"
	mov	r10d, DWORD PTR 80[rsp]
	jmp	.L69
.L130:
	lea	rcx, .LC27[rip]
	call	"getenv"
	mov	r10d, DWORD PTR 80[rsp]
	test	rax, rax
	je	.L68
	mov	r8d, 255
	mov	rdx, rax
	lea	rcx, 560[rsp]
	call	"strncpy"
	mov	r10d, DWORD PTR 80[rsp]
	jmp	.L68
.L129:
	lea	rcx, .LC25[rip]
	call	"getenv"
	mov	r10d, DWORD PTR 80[rsp]
	test	rax, rax
	je	.L67
	mov	r8d, 255
	mov	rdx, rax
	lea	rcx, 304[rsp]
	call	"strncpy"
	mov	r10d, DWORD PTR 80[rsp]
	jmp	.L67
.L135:
	mov	rcx, r14
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 45
	mov	edx, 1
	lea	rcx, .LC38[rip]
	mov	r9, rax
	call	"fwrite"
	jmp	.L77
.L127:
	mov	rcx, rbp
	call	"fclose"
.L95:
	mov	rcx, rsi
	call	"fclose"
	mov	rcx, r14
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 63
	mov	edx, 1
	lea	rcx, .LC66[rip]
	mov	r9, rax
	call	"fwrite"
	jmp	.L77
.L93:
	mov	r9, rsi
	mov	r8d, 4
	mov	edx, 1
	lea	rcx, .LC53[rip]
	call	"fwrite"
	jmp	.L94
.L91:
	mov	r9, rsi
	mov	r8d, 4
	mov	edx, 1
	lea	rcx, .LC53[rip]
	call	"fwrite"
	jmp	.L92
.L134:
	mov	rcx, r14
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 39
	mov	edx, 1
	lea	rcx, .LC37[rip]
	mov	r9, rax
	call	"fwrite"
	jmp	.L77
.L136:
	add	ecx, DWORD PTR 10148[rsp]
	jmp	.L80
.L137:
	lea	rax, 136[rsp]
	mov	rcx, QWORD PTR 10064[rsp]
	xor	r8d, r8d
	lea	r9, 240[rsp]
	mov	QWORD PTR 40[rsp], rax
	lea	rax, 816[rsp]
	lea	rdx, .LC43[rip]
	mov	QWORD PTR 32[rsp], rax
	call	[QWORD PTR __imp_RegQueryValueExA[rip]]
	mov	rcx, QWORD PTR 10064[rsp]
	call	[QWORD PTR __imp_RegCloseKey[rip]]
	jmp	.L82
.L140:
	mov	rcx, r14
	mov	DWORD PTR 80[rsp], eax
	call	"free"
	lea	rcx, .LC68[rip]
	call	"puts"
	mov	r10d, DWORD PTR 80[rsp]
	jmp	.L61
.L88:
	lea	rdx, .LC20[rip]
	cmp	ax, 12
	je	.L87
.L89:
	mov	r9, rsi
	mov	r8d, 4
	mov	edx, 1
	lea	rcx, .LC53[rip]
	call	"fwrite"
	jmp	.L90
.L102:
	lea	rdx, .LC17[rip]
	jmp	.L87
.L103:
	lea	rdx, .LC19[rip]
	jmp	.L87
.L138:
	mov	rcx, r14
	call	"free"
	call	[QWORD PTR __imp__errno[rip]]
	mov	ecx, DWORD PTR [rax]
	call	[QWORD PTR __imp_strerror[rip]]
	mov	ecx, 2
	mov	rbx, rax
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8, rbx
	lea	rdx, .LC45[rip]
	mov	rcx, rax
	call	"fprintf"
	jmp	.L77
.L133:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 46
	mov	edx, 1
	lea	rcx, .LC32[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 80[rsp]
	jmp	.L61
	.seh_endproc
.lcomm "timer_frequency",8,8
	.section .rdata,"dr"
	.align 8
.LC1:
	.long	0
	.long	1083129856
	.align 8
.LC2:
	.long	0
	.long	1071644672
	.align 8
.LC13:
	.long	0
	.long	1078525952
	.align 16
.LC16:
	.quad	0
	.quad	1
	.align 16
.LC33:
	.quad	2
	.quad	2
	.align 16
.LC34:
	.long	1
	.long	1
	.long	1
	.long	1
	.align 16
.LC35:
	.quad	4
	.quad	4
	.def	"__main";	.scl	2;	.type	32;	.endef
	.ident	"GCC: (Rev5, Built by MSYS2 project) 16.1.0"
	.def	"fputc";	.scl	2;	.type	32;	.endef
	.def	"fwrite";	.scl	2;	.type	32;	.endef
	.def	"fprintf";	.scl	2;	.type	32;	.endef
	.def	"qsort";	.scl	2;	.type	32;	.endef
	.def	"strlen";	.scl	2;	.type	32;	.endef
	.def	"strncmp";	.scl	2;	.type	32;	.endef
	.def	"strncpy";	.scl	2;	.type	32;	.endef
	.def	"snprintf";	.scl	2;	.type	32;	.endef
	.def	"sscanf";	.scl	2;	.type	32;	.endef
	.def	"malloc";	.scl	2;	.type	32;	.endef
	.def	"memcpy";	.scl	2;	.type	32;	.endef
	.def	"strftime";	.scl	2;	.type	32;	.endef
	.def	"fopen";	.scl	2;	.type	32;	.endef
	.def	"fwrite";	.scl	2;	.type	32;	.endef
	.def	"fread";	.scl	2;	.type	32;	.endef
	.def	"ferror";	.scl	2;	.type	32;	.endef
	.def	"fclose";	.scl	2;	.type	32;	.endef
	.def	"free";	.scl	2;	.type	32;	.endef
	.def	"getenv";	.scl	2;	.type	32;	.endef
	.def	"puts";	.scl	2;	.type	32;	.endef

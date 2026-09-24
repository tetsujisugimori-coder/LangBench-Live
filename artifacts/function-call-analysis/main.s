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
	.def	"optional_arg";	.scl	3;	.type	32;	.endef
	.seh_proc	"optional_arg"
"optional_arg":
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
	jle	.L18
	mov	rcx, r8
	lea	rbx, 40[r12]
	call	"strlen"
	mov	rbp, rax
	lea	eax, -6[rsi]
	lea	r12, 48[r12+rax*8]
	jmp	.L17
	.p2align 4,,10
	.p2align 3
.L16:
	add	rbx, 8
	cmp	rbx, r12
	je	.L18
.L17:
	mov	rsi, QWORD PTR [rbx]
	mov	r8, rbp
	mov	rdx, rdi
	mov	rcx, rsi
	call	"strncmp"
	test	eax, eax
	jne	.L16
	mov	rax, QWORD PTR 128[rsp]
	lea	rdx, [rsi+rbp]
	mov	rcx, r13
	lea	r8, -1[rax]
	call	"strncpy"
	mov	rax, QWORD PTR 128[rsp]
	mov	BYTE PTR -1[r13+rax], 0
	mov	eax, 1
	jmp	.L13
.L18:
	xor	eax, eax
.L13:
	add	rsp, 40
	pop	rbx
	pop	rsi
	pop	rdi
	pop	rbp
	pop	r12
	pop	r13
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
	jne	.L33
	jmp	.L22
	.p2align 4,,10
	.p2align 3
.L39:
	cmp	al, 9
	je	.L25
	movzx	r8d, al
	cmp	al, 10
	jne	.L27
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	lea	rcx, .LC5[rip]
	call	"fwrite"
.L31:
	movzx	eax, BYTE PTR 1[rbx]
	add	rbx, 1
	test	al, al
	je	.L22
.L33:
	cmp	al, 13
	je	.L23
	jbe	.L39
	cmp	al, 34
	je	.L28
	cmp	al, 92
	jne	.L40
	mov	r9, rsi
	mov	edx, 1
	add	rbx, 1
	mov	r8d, 2
	lea	rcx, .LC4[rip]
	call	"fwrite"
	movzx	eax, BYTE PTR [rbx]
	test	al, al
	jne	.L33
.L22:
	mov	rdx, rsi
	mov	ecx, 34
	add	rsp, 40
	pop	rbx
	pop	rsi
	jmp	"fputc"
	.p2align 4,,10
	.p2align 3
.L23:
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	lea	rcx, .LC6[rip]
	call	"fwrite"
	jmp	.L31
	.p2align 4,,10
	.p2align 3
.L25:
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	lea	rcx, .LC7[rip]
	call	"fwrite"
	jmp	.L31
	.p2align 4,,10
	.p2align 3
.L28:
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	lea	rcx, .LC3[rip]
	call	"fwrite"
	jmp	.L31
	.p2align 4,,10
	.p2align 3
.L40:
	movzx	r8d, al
	cmp	al, 31
	jbe	.L27
	mov	rdx, rsi
	mov	ecx, r8d
	call	"fputc"
	jmp	.L31
	.p2align 4,,10
	.p2align 3
.L27:
	lea	rdx, .LC8[rip]
	mov	rcx, rsi
	call	"fprintf"
	jmp	.L31
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
.L42:
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
	jne	.L42
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
	jmp	.L44
	.p2align 4,,10
	.p2align 3
.L49:
	lea	r9, .LC10[rip]
	movq	xmm2, r8
	mov	rcx, rdi
	add	rbx, 8
	lea	rdx, .LC11[rip]
	call	"fprintf"
	cmp	rbx, rsi
	je	.L45
.L44:
	mov	r8, QWORD PTR [rbx]
	cmp	rbp, rbx
	jne	.L49
	lea	r9, .LC14[rip]
	movq	xmm2, r8
	lea	rdx, .LC11[rip]
	mov	rcx, rdi
	call	"fprintf"
.L45:
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
	.ascii "direct\0"
.LC18:
	.ascii "function_call\0"
.LC19:
	.ascii "x64\0"
.LC20:
	.ascii "arm\0"
.LC21:
	.ascii "x86\0"
.LC22:
	.ascii "arm64\0"
.LC23:
	.ascii "%lf\0"
	.align 8
.LC24:
	.ascii "status=error\12message=expected build and optimization analysis arguments\12\0"
.LC25:
	.ascii "--measurement-order=\0"
.LC26:
	.ascii "function_call_first\0"
.LC27:
	.ascii "direct_first\0"
	.align 8
.LC28:
	.ascii "status=error\12message=invalid measurement order\12\0"
.LC29:
	.ascii "--result-path=\0"
	.align 8
.LC30:
	.ascii "status=error\12message=reverse order requires diagnostic result path\12\0"
	.align 8
.LC31:
	.ascii "status=error\12message=high-resolution timer is unavailable\12\0"
	.align 2
.LC32:
	.ascii "n\0t\0d\0l\0l\0.\0d\0l\0l\0\0\0"
.LC33:
	.ascii "RtlGetVersion\0"
.LC34:
	.ascii "%lu.%lu.%lu\0"
.LC35:
	.ascii "--experiment-id=\0"
	.align 8
.LC36:
	.ascii "status=error\12message=failed to get OS version via RtlGetVersion\12\0"
.LC37:
	.ascii "LANGBENCH_EXPERIMENT_ID\0"
.LC38:
	.ascii "--run-id=\0"
.LC39:
	.ascii "LANGBENCH_RUN_ID\0"
.LC40:
	.ascii "%s_%s\0"
.LC41:
	.ascii "function_call_numeric_sum\0"
.LC42:
	.ascii "%s_%s_%s\0"
.LC43:
	.ascii "c\0"
	.align 8
.LC44:
	.ascii "status=error\12message=failed to allocate array\12\0"
	.align 8
.LC48:
	.ascii "status=error\12message=checksum mismatch\12\0"
	.align 8
.LC49:
	.ascii "status=error\12message=failed to get cwd\12\0"
	.align 8
.LC50:
	.ascii "status=error\12message=result path is too long\12\0"
	.align 8
.LC51:
	.ascii "results\\function_call_numeric_sum_c_result.json\0"
.LC52:
	.ascii "%Y-%m-%dT%H:%M:%S\0"
.LC53:
	.ascii "%s%c%02d:%02d\0"
	.align 8
.LC54:
	.ascii "HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0\0"
.LC55:
	.ascii "ProcessorNameString\0"
.LC56:
	.ascii "wb\0"
	.align 8
.LC57:
	.ascii "status=error\12message=failed to open result: %s\12\0"
	.align 8
.LC58:
	.ascii "{\12  \"type\": \"langbench_result\",\12  \"schema_version\": \"1.0\",\12  \"project\": \"LangBench Live\",\12  \"benchmark\": \"%s\",\12  \"experiment_id\": \0"
.LC59:
	.ascii ",\12  \"run_id\": \0"
	.align 8
.LC60:
	.ascii ",\12  \"language\": \"c\",\12  \"created_at\": \0"
	.align 8
.LC61:
	.ascii ",\12  \"status\": \"success\",\12  \"engine\": {\"runtime\": \"native\", \"runtime_version\": null},\12  \"execution\": {\"runner\": \"vscode_terminal_powershell\", \"runner_label\": \"VSCode Terminal / PowerShell\", \"cwd\": \0"
.LC62:
	.ascii ", \"argv\": [\0"
.LC63:
	.ascii ", \0"
.LC64:
	.ascii "], \"measurement_order\": [\0"
	.align 8
.LC65:
	.ascii "]},\12  \"environment\": {\"os\": \"Windows\", \"os_version\": \0"
.LC66:
	.ascii ", \"architecture\": \0"
.LC67:
	.ascii "null\0"
.LC68:
	.ascii ", \"cpu\": \0"
	.align 8
.LC69:
	.ascii ", \"logical_processors\": %lu, \"memory_bytes\": \0"
.LC70:
	.ascii "%llu\0"
	.align 8
.LC71:
	.ascii "},\12  \"build\": {\"required\": true, \"compiler\": \"gcc\", \"compiler_version\": \0"
.LC72:
	.ascii ", \"compile_command\": \0"
	.align 8
.LC73:
	.ascii ", \"compile_ms\": %.3f, \"source_path\": \0"
	.align 8
.LC74:
	.ascii "},\12  \"optimization_analysis\": \0"
.LC75:
	.ascii "rb\0"
.LC76:
	.ascii ",\12\0"
	.align 8
.LC77:
	.ascii "  \"config\": {\"item_count\": %d, \"warmup_iterations\": %d, \"measurement_iterations\": %d, \"numeric_type\": \"integer\", \"value_field\": \"value\", \"cases\": [\"direct\", \"function_call\"]},\12  \"timing\": {\"process_startup_ms\": null, \"setup_ms\": %.3f, \"warmup_ms\": %.3f, \"measurement_ms\": %.3f, \"benchmark_total_ms\": %.3f},\12  \"results\": {\"direct\": \0"
.LC78:
	.ascii ", \"function_call\": \0"
	.align 8
.LC79:
	.ascii "},\12  \"validation\": {\"direct_checksum\": %lld, \"function_call_checksum\": %lld, \"expected_checksum\": %lld, \"tolerance\": 0, \"passed\": true},\12  \"error\": null\12}\12\0"
	.align 8
.LC80:
	.ascii "status=error\12message=failed to read optimization analysis JSON\12\0"
	.align 8
.LC81:
	.ascii "status=error\12message=failed to finish writing result JSON\12\0"
.LC82:
	.ascii "status=success\0"
	.section	.text.startup,"x"
	.p2align 4
	.globl	"main"
	.def	"main";	.scl	2;	.type	32;	.endef
	.seh_proc	"main"
"main":
	push	r15
	.seh_pushreg	r15
	mov	eax, 18440
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
	call	___chkstk_ms
	sub	rsp, rax
	.seh_stackalloc	18440
	movups	XMMWORD PTR 18368[rsp], xmm6
	.seh_savexmm	xmm6, 18368
	movups	XMMWORD PTR 18384[rsp], xmm7
	.seh_savexmm	xmm7, 18384
	movups	XMMWORD PTR 18400[rsp], xmm8
	.seh_savexmm	xmm8, 18400
	movups	XMMWORD PTR 18416[rsp], xmm9
	.seh_savexmm	xmm9, 18416
	.seh_endprologue
	mov	ebp, ecx
	mov	rbx, rdx
	call	"__main"
	pxor	xmm0, xmm0
	xor	edx, edx
	mov	r8d, 4096
	lea	rcx, 10176[rsp]
	movups	XMMWORD PTR 416[rsp], xmm0
	mov	QWORD PTR 136[rsp], 0
	mov	QWORD PTR 144[rsp], 0
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
	movups	XMMWORD PTR 1072[rsp], xmm0
	movups	XMMWORD PTR 1088[rsp], xmm0
	movups	XMMWORD PTR 1104[rsp], xmm0
	movups	XMMWORD PTR 1120[rsp], xmm0
	movups	XMMWORD PTR 1136[rsp], xmm0
	movups	XMMWORD PTR 1152[rsp], xmm0
	movups	XMMWORD PTR 1168[rsp], xmm0
	movups	XMMWORD PTR 160[rsp], xmm0
	movups	XMMWORD PTR 176[rsp], xmm0
	call	"memset"
	cmp	ebp, 5
	jle	.L62
	mov	rcx, QWORD PTR 8[rbx]
	lea	r8, 112[rsp]
	lea	rdx, .LC23[rip]
	call	"sscanf"
	mov	r10d, eax
	cmp	eax, 1
	je	.L162
.L62:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 72
	mov	edx, 1
	lea	rcx, .LC24[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, 1
.L61:
	movups	xmm6, XMMWORD PTR 18368[rsp]
	mov	eax, r10d
	movups	xmm7, XMMWORD PTR 18384[rsp]
	movups	xmm8, XMMWORD PTR 18400[rsp]
	movups	xmm9, XMMWORD PTR 18416[rsp]
	add	rsp, 18440
	pop	rbx
	pop	rsi
	pop	rdi
	pop	rbp
	pop	r12
	pop	r13
	pop	r14
	pop	r15
	ret
.L162:
	pxor	xmm0, xmm0
	comisd	xmm0, QWORD PTR 112[rsp]
	ja	.L62
	mov	rax, QWORD PTR 16[rbx]
	cmp	BYTE PTR [rax], 0
	je	.L62
	mov	rax, QWORD PTR 24[rbx]
	cmp	BYTE PTR [rax], 0
	je	.L62
	mov	rax, QWORD PTR 32[rbx]
	cmp	BYTE PTR [rax], 0
	je	.L62
	mov	rax, QWORD PTR 40[rbx]
	cmp	BYTE PTR [rax], 0
	je	.L62
	mov	QWORD PTR 32[rsp], 32
	lea	r9, 160[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	lea	r8, .LC25[rip]
	mov	DWORD PTR 88[rsp], r10d
	call	"optional_arg"
	lea	rdx, .LC26[rip]
	lea	rcx, 160[rsp]
	call	"strcmp"
	cmp	BYTE PTR 160[rsp], 0
	mov	r10d, DWORD PTR 88[rsp]
	mov	r14d, eax
	je	.L65
	test	eax, eax
	je	.L66
	lea	rdx, .LC27[rip]
	lea	rcx, 160[rsp]
	call	"strcmp"
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	jne	.L163
.L67:
	mov	QWORD PTR 32[rsp], 4096
	lea	r9, 10176[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	lea	r8, .LC29[rip]
	mov	DWORD PTR 88[rsp], r10d
	call	"optional_arg"
	movzx	esi, BYTE PTR 10176[rsp]
	mov	r10d, DWORD PTR 88[rsp]
.L69:
	mov	DWORD PTR 88[rsp], r10d
	lea	rcx, "timer_frequency"[rip]
	call	[QWORD PTR __imp_QueryPerformanceFrequency[rip]]
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	je	.L71
	cmp	QWORD PTR "timer_frequency"[rip], 0
	je	.L71
	mov	DWORD PTR 88[rsp], r10d
	lea	rcx, .LC32[rip]
	call	[QWORD PTR __imp_GetModuleHandleW[rip]]
	mov	r10d, DWORD PTR 88[rsp]
	test	rax, rax
	je	.L73
	lea	rdx, .LC33[rip]
	mov	rcx, rax
	call	[QWORD PTR __imp_GetProcAddress[rip]]
	mov	r10d, DWORD PTR 88[rsp]
	test	rax, rax
	je	.L73
	xor	edx, edx
	mov	r8d, 276
	mov	QWORD PTR 96[rsp], rax
	lea	rcx, 14272[rsp]
	call	"memset"
	lea	rcx, 14272[rsp]
	mov	DWORD PTR 14272[rsp], 276
	call	[QWORD PTR 96[rsp]]
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	je	.L164
.L73:
	mov	DWORD PTR 88[rsp], r10d
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 64
	mov	edx, 1
	lea	rcx, .LC36[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L61
.L65:
	test	eax, eax
	jne	.L67
.L66:
	mov	QWORD PTR 32[rsp], 4096
	lea	r9, 10176[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	lea	r8, .LC29[rip]
	mov	DWORD PTR 88[rsp], r10d
	call	"optional_arg"
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	je	.L68
	movzx	esi, BYTE PTR 10176[rsp]
	jmp	.L69
.L71:
	mov	DWORD PTR 88[rsp], r10d
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 58
	mov	edx, 1
	lea	rcx, .LC31[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L61
.L164:
	mov	eax, DWORD PTR 14284[rsp]
	mov	r9d, DWORD PTR 14276[rsp]
	lea	r8, .LC34[rip]
	mov	edx, 64
	lea	rcx, 288[rsp]
	mov	DWORD PTR 40[rsp], eax
	mov	eax, DWORD PTR 14280[rsp]
	mov	DWORD PTR 32[rsp], eax
	call	"snprintf"
	lea	r9, 416[rsp]
	lea	r8, .LC35[rip]
	mov	ecx, ebp
	mov	QWORD PTR 32[rsp], 256
	mov	rdx, rbx
	call	"optional_arg"
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	je	.L165
.L76:
	mov	QWORD PTR 32[rsp], 256
	lea	r9, 672[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	lea	r8, .LC38[rip]
	mov	DWORD PTR 88[rsp], r10d
	call	"optional_arg"
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	je	.L166
.L77:
	cmp	BYTE PTR 416[rsp], 0
	je	.L167
.L78:
	cmp	BYTE PTR 672[rsp], 0
	je	.L168
.L79:
	mov	DWORD PTR 88[rsp], r10d
	call	"now_ms"
	mov	ecx, 4000000
	movapd	xmm6, xmm0
	call	"malloc"
	mov	r10d, DWORD PTR 88[rsp]
	test	rax, rax
	mov	r15, rax
	je	.L169
	movdqu	xmm0, XMMWORD PTR .LC16[rip]
	movdqu	xmm5, XMMWORD PTR .LC45[rip]
	lea	rdx, 4000000[rax]
	movdqu	xmm4, XMMWORD PTR .LC46[rip]
	movdqu	xmm3, XMMWORD PTR .LC47[rip]
	.p2align 6
	.p2align 4
	.p2align 3
.L81:
	movdqa	xmm2, xmm0
	movdqa	xmm1, xmm0
	paddq	xmm0, xmm3
	add	rax, 16
	paddq	xmm2, xmm5
	shufps	xmm1, xmm2, 136
	paddd	xmm1, xmm4
	movups	XMMWORD PTR -16[rax], xmm1
	cmp	rax, rdx
	jne	.L81
	mov	DWORD PTR 88[rsp], r10d
	call	"now_ms"
	movapd	xmm7, xmm0
	test	r14d, r14d
	jne	.L82
	lea	rax, 144[rsp]
	lea	r9, 1584[rsp]
	mov	rcx, r15
	mov	QWORD PTR 32[rsp], rax
	lea	r8, 128[rsp]
	lea	rdx, "function_call_sum"[rip]
	mov	r12, r9
	call	"measure.constprop.0"
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	je	.L83
	lea	rax, 136[rsp]
	lea	r9, 1184[rsp]
	mov	QWORD PTR 32[rsp], rax
	mov	r13, r9
	lea	r8, 120[rsp]
	lea	rdx, "direct_sum"[rip]
.L160:
	mov	rcx, r15
	call	"measure.constprop.0"
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	je	.L83
	mov	rcx, r13
	mov	DWORD PTR 88[rsp], r10d
	lea	rdx, 1984[rsp]
	call	"sample_total"
	mov	rcx, r12
	movapd	xmm8, xmm0
	call	"sample_total"
	mov	ecx, 4096
	movapd	xmm9, xmm0
	call	[QWORD PTR __imp_GetCurrentDirectoryA[rip]]
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	je	.L170
	test	sil, sil
	je	.L171
	lea	rax, 6080[rsp]
	lea	rdx, 10176[rsp]
	mov	DWORD PTR 96[rsp], r10d
	mov	rcx, rax
	mov	BYTE PTR 10176[rsp], sil
	mov	QWORD PTR 88[rsp], rax
	call	"strcpy"
	mov	r10d, DWORD PTR 96[rsp]
.L88:
	xor	ecx, ecx
	mov	DWORD PTR 96[rsp], r10d
	call	_time64
	lea	rdx, 152[rsp]
	lea	rcx, 352[rsp]
	mov	QWORD PTR 152[rsp], rax
	call	_localtime64_s
	lea	r9, 352[rsp]
	lea	r8, .LC52[rip]
	mov	edx, 32
	lea	rcx, 240[rsp]
	call	"strftime"
	lea	rcx, 14272[rsp]
	call	[QWORD PTR __imp_GetTimeZoneInformation[rip]]
	mov	ecx, DWORD PTR 14272[rsp]
	mov	r10d, DWORD PTR 96[rsp]
	cmp	eax, 1
	je	.L172
	mov	edx, ecx
	add	ecx, DWORD PTR 14440[rsp]
	cmp	eax, 2
	cmovne	ecx, edx
.L90:
	mov	eax, ecx
	mov	r8d, 60
	mov	DWORD PTR 96[rsp], r10d
	neg	eax
	lea	r9, 240[rsp]
	cmovs	eax, ecx
	cdq
	idiv	r8d
	test	ecx, ecx
	lea	r8, .LC53[rip]
	setg	cl
	movzx	ecx, cl
	lea	ecx, 43[rcx+rcx]
	mov	DWORD PTR 32[rsp], ecx
	lea	rcx, 192[rsp]
	mov	DWORD PTR 48[rsp], edx
	mov	edx, 48
	mov	DWORD PTR 40[rsp], eax
	call	"snprintf"
	xor	edx, edx
	xor	ecx, ecx
	xor	r8d, r8d
	lea	rax, 14272[rsp]
	mov	QWORD PTR 14272[rsp], rdx
	mov	r9d, 131097
	lea	rdx, .LC54[rip]
	mov	DWORD PTR 352[rsp], ecx
	mov	rcx, -2147483646
	mov	DWORD PTR 152[rsp], 256
	mov	BYTE PTR 928[rsp], 0
	mov	QWORD PTR 32[rsp], rax
	call	[QWORD PTR __imp_RegOpenKeyExA[rip]]
	mov	r10d, DWORD PTR 96[rsp]
	test	eax, eax
	je	.L173
.L92:
	mov	DWORD PTR 96[rsp], r10d
	lea	rcx, 240[rsp]
	call	[QWORD PTR __imp_GetNativeSystemInfo[rip]]
	lea	rcx, 352[rsp]
	mov	DWORD PTR 352[rsp], 64
	call	[QWORD PTR __imp_GlobalMemoryStatusEx[rip]]
	mov	r10d, DWORD PTR 96[rsp]
	test	eax, eax
	jne	.L93
	xor	eax, eax
	mov	QWORD PTR 360[rsp], rax
.L93:
	mov	rcx, QWORD PTR 88[rsp]
	lea	rdx, .LC56[rip]
	mov	DWORD PTR 96[rsp], r10d
	call	"fopen"
	mov	r10d, DWORD PTR 96[rsp]
	test	rax, rax
	mov	rsi, rax
	mov	DWORD PTR 88[rsp], r10d
	je	.L174
	lea	r8, .LC41[rip]
	lea	rdx, .LC58[rip]
	mov	rcx, rax
	call	"fprintf"
	lea	rdx, 416[rsp]
	mov	rcx, rsi
	lea	edi, -1[rbp]
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 14
	mov	edx, 1
	lea	rcx, .LC59[rip]
	call	"fwrite"
	lea	rdx, 672[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 37
	mov	edx, 1
	lea	rcx, .LC60[rip]
	call	"fwrite"
	lea	rdx, 192[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 196
	mov	edx, 1
	lea	rcx, .LC61[rip]
	call	"fwrite"
	lea	rdx, 1984[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 11
	mov	edx, 1
	lea	rcx, .LC62[rip]
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	xor	r11d, r11d
	jmp	.L96
.L175:
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	mov	DWORD PTR 88[rsp], r10d
	lea	rcx, .LC63[rip]
	mov	QWORD PTR 96[rsp], r11
	call	"fwrite"
	mov	r11, QWORD PTR 96[rsp]
	mov	r10d, DWORD PTR 88[rsp]
	add	r11, 1
	cmp	ebp, r11d
	jle	.L95
.L96:
	mov	rdx, QWORD PTR [rbx+r11*8]
	mov	rcx, rsi
	mov	DWORD PTR 96[rsp], r10d
	mov	QWORD PTR 88[rsp], r11
	call	"write_json_string"
	mov	r11, QWORD PTR 88[rsp]
	mov	r10d, DWORD PTR 96[rsp]
	cmp	rdi, r11
	jne	.L175
.L95:
	mov	r9, rsi
	mov	r8d, 25
	mov	edx, 1
	mov	DWORD PTR 88[rsp], r10d
	lea	rcx, .LC64[rip]
	call	"fwrite"
	test	r14d, r14d
	jne	.L176
	lea	rdx, .LC18[rip]
	mov	rcx, rsi
	call	"write_json_string"
	mov	edx, 1
	mov	r9, rsi
	mov	r8d, 2
	lea	rcx, .LC63[rip]
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	lea	rdx, .LC17[rip]
.L113:
	mov	rcx, rsi
	mov	DWORD PTR 88[rsp], r10d
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 53
	mov	edx, 1
	lea	rcx, .LC65[rip]
	call	"fwrite"
	lea	rdx, 288[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 18
	mov	edx, 1
	lea	rcx, .LC66[rip]
	call	"fwrite"
	movzx	eax, WORD PTR 240[rsp]
	mov	r10d, DWORD PTR 88[rsp]
	cmp	ax, 9
	je	.L115
	ja	.L100
	test	ax, ax
	je	.L116
	lea	rdx, .LC20[rip]
	cmp	ax, 5
	jne	.L101
.L99:
	mov	rcx, rsi
	mov	DWORD PTR 88[rsp], r10d
	call	"write_json_string"
	mov	r10d, DWORD PTR 88[rsp]
.L102:
	mov	r9, rsi
	mov	r8d, 9
	mov	edx, 1
	mov	DWORD PTR 88[rsp], r10d
	lea	rcx, .LC68[rip]
	call	"fwrite"
	cmp	BYTE PTR 928[rsp], 0
	je	.L103
	lea	rdx, 928[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r10d, DWORD PTR 88[rsp]
.L104:
	mov	r8d, DWORD PTR 272[rsp]
	lea	rdx, .LC69[rip]
	mov	rcx, rsi
	mov	DWORD PTR 88[rsp], r10d
	call	"fprintf"
	mov	r8, QWORD PTR 360[rsp]
	test	r8, r8
	je	.L105
	lea	rdx, .LC70[rip]
	mov	rcx, rsi
	call	"fprintf"
	mov	r10d, DWORD PTR 88[rsp]
.L106:
	mov	r9, rsi
	mov	r8d, 72
	mov	edx, 1
	mov	DWORD PTR 88[rsp], r10d
	lea	rcx, .LC71[rip]
	call	"fwrite"
	mov	rdx, QWORD PTR 16[rbx]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 21
	mov	edx, 1
	lea	rcx, .LC72[rip]
	call	"fwrite"
	mov	rdx, QWORD PTR 24[rbx]
	mov	rcx, rsi
	call	"write_json_string"
	movsd	xmm2, QWORD PTR 112[rsp]
	lea	rdx, .LC73[rip]
	mov	rcx, rsi
	movq	r8, xmm2
	call	"fprintf"
	mov	rdx, QWORD PTR 32[rbx]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 30
	mov	edx, 1
	lea	rcx, .LC74[rip]
	call	"fwrite"
	mov	rcx, QWORD PTR 40[rbx]
	lea	rdx, .LC75[rip]
	call	"fopen"
	mov	r10d, DWORD PTR 88[rsp]
	test	rax, rax
	mov	rbp, rax
	jne	.L108
	jmp	.L107
.L109:
	mov	r9, rsi
	mov	r8, rbx
	mov	edx, 1
	lea	rcx, 14272[rsp]
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	cmp	rbx, rax
	jne	.L161
.L108:
	mov	r9, rbp
	mov	r8d, 4096
	mov	edx, 1
	mov	DWORD PTR 88[rsp], r10d
	lea	rcx, 14272[rsp]
	call	"fread"
	mov	rbx, rax
	test	rax, rax
	jne	.L109
	mov	rcx, rbp
	call	"ferror"
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	jne	.L161
	movapd	xmm0, xmm7
	pxor	xmm4, xmm4
	pxor	xmm5, xmm5
	mov	rcx, rbp
	subsd	xmm0, xmm6
	movsd	xmm2, QWORD PTR .LC1[rip]
	mov	DWORD PTR 108[rsp], r10d
	mulsd	xmm0, xmm2
	addsd	xmm0, QWORD PTR .LC2[rip]
	cvttsd2si	rax, xmm0
	movapd	xmm0, xmm8
	addsd	xmm0, xmm9
	mulsd	xmm0, xmm2
	cvtsi2sd	xmm4, rax
	addsd	xmm0, QWORD PTR .LC2[rip]
	divsd	xmm4, xmm2
	cvttsd2si	rax, xmm0
	cvtsi2sd	xmm5, rax
	divsd	xmm5, xmm2
	movsd	QWORD PTR 96[rsp], xmm4
	movsd	QWORD PTR 88[rsp], xmm5
	call	"fclose"
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	lea	rcx, .LC76[rip]
	call	"fwrite"
	movsd	xmm1, QWORD PTR 120[rsp]
	mov	rcx, rsi
	movsd	xmm4, QWORD PTR 96[rsp]
	movsd	xmm3, QWORD PTR 128[rsp]
	movsd	xmm5, QWORD PTR 88[rsp]
	mov	DWORD PTR 32[rsp], 50
	mov	r9d, 5
	movapd	xmm0, xmm1
	movsd	xmm2, QWORD PTR .LC1[rip]
	movsd	QWORD PTR 40[rsp], xmm4
	mov	r8d, 1000000
	addsd	xmm0, xmm4
	addsd	xmm1, xmm3
	movsd	QWORD PTR 56[rsp], xmm5
	lea	rdx, .LC77[rip]
	addsd	xmm0, xmm3
	mulsd	xmm1, xmm2
	addsd	xmm1, QWORD PTR .LC2[rip]
	addsd	xmm0, xmm5
	mulsd	xmm0, xmm2
	addsd	xmm0, QWORD PTR .LC2[rip]
	cvttsd2si	rax, xmm0
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, rax
	divsd	xmm0, xmm2
	cvttsd2si	rax, xmm1
	movsd	QWORD PTR 64[rsp], xmm0
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, rax
	divsd	xmm0, xmm2
	movsd	QWORD PTR 48[rsp], xmm0
	call	"fprintf"
	mov	rdx, r13
	mov	rcx, rsi
	call	"write_case"
	mov	r9, rsi
	mov	r8d, 19
	mov	edx, 1
	lea	rcx, .LC78[rip]
	call	"fwrite"
	mov	rdx, r12
	mov	rcx, rsi
	call	"write_case"
	mov	r9, QWORD PTR 144[rsp]
	mov	r8, QWORD PTR 136[rsp]
	mov	rcx, rsi
	movabs	rax, 500000500000
	lea	rdx, .LC79[rip]
	mov	QWORD PTR 32[rsp], rax
	call	"fprintf"
	mov	rcx, rsi
	call	"ferror"
	mov	rcx, rsi
	mov	ebx, eax
	call	"fclose"
	mov	r10d, DWORD PTR 108[rsp]
	or	eax, ebx
	je	.L177
	mov	rcx, r15
	mov	DWORD PTR 88[rsp], r10d
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 58
	mov	edx, 1
	lea	rcx, .LC81[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L61
.L68:
	mov	DWORD PTR 88[rsp], r10d
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 67
	mov	edx, 1
	lea	rcx, .LC30[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L61
.L83:
	mov	rcx, r15
	mov	DWORD PTR 88[rsp], r10d
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 39
	mov	edx, 1
	lea	rcx, .LC48[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L61
.L82:
	lea	rax, 136[rsp]
	lea	r8, 120[rsp]
	mov	rcx, r15
	mov	QWORD PTR 32[rsp], rax
	lea	r9, 1184[rsp]
	lea	rdx, "direct_sum"[rip]
	mov	r13, r9
	call	"measure.constprop.0"
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	je	.L83
	lea	r9, 1584[rsp]
	lea	rax, 144[rsp]
	mov	QWORD PTR 32[rsp], rax
	mov	r12, r9
	lea	r8, 128[rsp]
	lea	rdx, "function_call_sum"[rip]
	jmp	.L160
.L168:
	lea	rcx, 14272[rsp]
	mov	DWORD PTR 88[rsp], r10d
	call	"timestamp_id.constprop.0"
	lea	rax, .LC41[rip]
	mov	edx, 256
	lea	r9, 14272[rsp]
	mov	QWORD PTR 40[rsp], rax
	lea	rax, .LC43[rip]
	lea	r8, .LC42[rip]
	mov	QWORD PTR 32[rsp], rax
	lea	rcx, 672[rsp]
	call	"snprintf"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L79
.L167:
	lea	rcx, 14272[rsp]
	mov	DWORD PTR 88[rsp], r10d
	call	"timestamp_id.constprop.0"
	lea	rax, .LC41[rip]
	mov	edx, 256
	lea	r9, 14272[rsp]
	mov	QWORD PTR 32[rsp], rax
	lea	r8, .LC40[rip]
	lea	rcx, 416[rsp]
	call	"snprintf"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L78
.L166:
	lea	rcx, .LC39[rip]
	call	"getenv"
	mov	r10d, DWORD PTR 88[rsp]
	test	rax, rax
	je	.L77
	mov	r8d, 255
	mov	rdx, rax
	lea	rcx, 672[rsp]
	call	"strncpy"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L77
.L165:
	lea	rcx, .LC37[rip]
	mov	DWORD PTR 88[rsp], r10d
	call	"getenv"
	mov	r10d, DWORD PTR 88[rsp]
	test	rax, rax
	je	.L76
	mov	r8d, 255
	mov	rdx, rax
	lea	rcx, 416[rsp]
	call	"strncpy"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L76
.L163:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 47
	mov	edx, 1
	lea	rcx, .LC28[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L61
.L171:
	lea	rcx, 1984[rsp]
	mov	DWORD PTR 88[rsp], r10d
	call	"strlen"
	mov	r10d, DWORD PTR 88[rsp]
	mov	r8, rax
	lea	rax, 49[rax]
	cmp	rax, 4096
	ja	.L178
	lea	rdi, 6080[rsp]
	lea	rdx, 1984[rsp]
	mov	DWORD PTR 108[rsp], r10d
	mov	rcx, rdi
	mov	QWORD PTR 88[rsp], rdi
	lea	rsi, .LC51[rip]
	mov	QWORD PTR 96[rsp], r8
	call	"memcpy"
	mov	r8, QWORD PTR 96[rsp]
	mov	ecx, DWORD PTR .LC51[rip+44]
	mov	BYTE PTR [rdi+r8], 92
	mov	DWORD PTR 45[rdi+r8], ecx
	mov	ecx, 11
	lea	rdi, 1[rdi+r8]
	rep movsd
	mov	r10d, DWORD PTR 108[rsp]
	jmp	.L88
.L176:
	lea	rdx, .LC17[rip]
	mov	rcx, rsi
	call	"write_json_string"
	mov	edx, 1
	mov	r9, rsi
	mov	r8d, 2
	lea	rcx, .LC63[rip]
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	lea	rdx, .LC18[rip]
	jmp	.L113
.L161:
	mov	rcx, rbp
	call	"fclose"
	mov	r10d, DWORD PTR 88[rsp]
.L107:
	mov	rcx, rsi
	mov	DWORD PTR 88[rsp], r10d
	call	"fclose"
	mov	rcx, r15
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 63
	mov	edx, 1
	lea	rcx, .LC80[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L61
.L105:
	mov	r9, rsi
	mov	r8d, 4
	mov	edx, 1
	lea	rcx, .LC67[rip]
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L106
.L103:
	mov	r9, rsi
	mov	r8d, 4
	mov	edx, 1
	lea	rcx, .LC67[rip]
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L104
.L172:
	add	ecx, DWORD PTR 14356[rsp]
	jmp	.L90
.L170:
	mov	rcx, r15
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 39
	mov	edx, 1
	lea	rcx, .LC49[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L61
.L173:
	lea	rax, 152[rsp]
	mov	rcx, QWORD PTR 14272[rsp]
	xor	r8d, r8d
	lea	r9, 352[rsp]
	mov	QWORD PTR 40[rsp], rax
	lea	rax, 928[rsp]
	lea	rdx, .LC55[rip]
	mov	QWORD PTR 32[rsp], rax
	call	[QWORD PTR __imp_RegQueryValueExA[rip]]
	mov	rcx, QWORD PTR 14272[rsp]
	call	[QWORD PTR __imp_RegCloseKey[rip]]
	mov	r10d, DWORD PTR 96[rsp]
	jmp	.L92
.L100:
	lea	rdx, .LC22[rip]
	cmp	ax, 12
	je	.L99
.L101:
	mov	r9, rsi
	mov	r8d, 4
	mov	edx, 1
	mov	DWORD PTR 88[rsp], r10d
	lea	rcx, .LC67[rip]
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L102
.L116:
	lea	rdx, .LC21[rip]
	jmp	.L99
.L115:
	lea	rdx, .LC19[rip]
	jmp	.L99
.L174:
	mov	rcx, r15
	call	"free"
	call	[QWORD PTR __imp__errno[rip]]
	mov	ecx, DWORD PTR [rax]
	call	[QWORD PTR __imp_strerror[rip]]
	mov	ecx, 2
	mov	rbx, rax
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8, rbx
	lea	rdx, .LC57[rip]
	mov	rcx, rax
	call	"fprintf"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L61
.L177:
	mov	rcx, r15
	call	"free"
	lea	rcx, .LC82[rip]
	call	"puts"
	xor	r10d, r10d
	jmp	.L61
.L178:
	mov	rcx, r15
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 45
	mov	edx, 1
	lea	rcx, .LC50[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L61
.L169:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 46
	mov	edx, 1
	lea	rcx, .LC44[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
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
.LC45:
	.quad	2
	.quad	2
	.align 16
.LC46:
	.long	1
	.long	1
	.long	1
	.long	1
	.align 16
.LC47:
	.quad	4
	.quad	4
	.def	"__main";	.scl	2;	.type	32;	.endef
	.ident	"GCC: (Rev5, Built by MSYS2 project) 16.1.0"
	.def	"strlen";	.scl	2;	.type	32;	.endef
	.def	"strncmp";	.scl	2;	.type	32;	.endef
	.def	"strncpy";	.scl	2;	.type	32;	.endef
	.def	"fputc";	.scl	2;	.type	32;	.endef
	.def	"fwrite";	.scl	2;	.type	32;	.endef
	.def	"fprintf";	.scl	2;	.type	32;	.endef
	.def	"qsort";	.scl	2;	.type	32;	.endef
	.def	"snprintf";	.scl	2;	.type	32;	.endef
	.def	"memset";	.scl	2;	.type	32;	.endef
	.def	"sscanf";	.scl	2;	.type	32;	.endef
	.def	"strcmp";	.scl	2;	.type	32;	.endef
	.def	"malloc";	.scl	2;	.type	32;	.endef
	.def	"strcpy";	.scl	2;	.type	32;	.endef
	.def	"strftime";	.scl	2;	.type	32;	.endef
	.def	"fopen";	.scl	2;	.type	32;	.endef
	.def	"fwrite";	.scl	2;	.type	32;	.endef
	.def	"fread";	.scl	2;	.type	32;	.endef
	.def	"ferror";	.scl	2;	.type	32;	.endef
	.def	"fclose";	.scl	2;	.type	32;	.endef
	.def	"free";	.scl	2;	.type	32;	.endef
	.def	"getenv";	.scl	2;	.type	32;	.endef
	.def	"memcpy";	.scl	2;	.type	32;	.endef
	.def	"puts";	.scl	2;	.type	32;	.endef

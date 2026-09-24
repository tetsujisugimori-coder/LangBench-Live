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
	jle	.L19
	mov	rcx, r8
	lea	rbx, 40[r12]
	call	"strlen"
	mov	rbp, rax
	lea	eax, -6[rsi]
	lea	r12, 48[r12+rax*8]
	jmp	.L18
	.p2align 4,,10
	.p2align 3
.L17:
	add	rbx, 8
	cmp	rbx, r12
	je	.L19
.L18:
	mov	rsi, QWORD PTR [rbx]
	mov	r8, rbp
	mov	rdx, rdi
	mov	rcx, rsi
	call	"strncmp"
	test	eax, eax
	jne	.L17
	mov	rax, QWORD PTR 128[rsp]
	lea	rdx, [rsi+rbp]
	mov	rcx, r13
	lea	r8, -1[rax]
	call	"strncpy"
	mov	rax, QWORD PTR 128[rsp]
	mov	BYTE PTR -1[r13+rax], 0
	mov	eax, 1
	jmp	.L14
.L19:
	xor	eax, eax
.L14:
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
	mov	rdi, QWORD PTR 224[rsp]
	mov	rbp, rcx
	mov	r12, rdx
	lea	rsi, 56[rsp]
	mov	r15, r8
	mov	QWORD PTR 216[rsp], r9
	cmp	QWORD PTR 232[rsp], 0
	je	.L69
	mov	rbx, QWORD PTR __imp_QueryPerformanceCounter[rip]
	mov	rcx, rsi
	call	rbx
	mov	rax, QWORD PTR 56[rsp]
	mov	rdx, QWORD PTR 232[rsp]
	mov	QWORD PTR 800[rdx], rax
.L52:
	mov	rcx, rsi
	mov	r13d, 5
	movabs	r14, 500000500000
	call	rbx
	mov	rax, QWORD PTR 56[rsp]
	mov	QWORD PTR 32[rsp], rax
	mov	rax, QWORD PTR "timer_frequency"[rip]
	mov	QWORD PTR 40[rsp], rax
.L54:
	mov	rcx, rbp
	call	r12
	cmp	rax, r14
	jne	.L53
	sub	r13d, 1
	jne	.L54
	movsd	xmm6, QWORD PTR .LC1[rip]
	pxor	xmm7, xmm7
	pxor	xmm0, xmm0
	mov	rcx, rsi
	cvtsi2sd	xmm7, QWORD PTR 32[rsp]
	cvtsi2sd	xmm0, QWORD PTR 40[rsp]
	mulsd	xmm7, xmm6
	divsd	xmm7, xmm0
	call	rbx
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, QWORD PTR 56[rsp]
	pxor	xmm1, xmm1
	cvtsi2sd	xmm1, QWORD PTR "timer_frequency"[rip]
	mulsd	xmm0, xmm6
	movsd	xmm8, QWORD PTR .LC2[rip]
	divsd	xmm0, xmm1
	subsd	xmm0, xmm7
	mulsd	xmm0, xmm6
	addsd	xmm0, xmm8
	cvttsd2si	rax, xmm0
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, rax
	divsd	xmm0, xmm6
	movsd	QWORD PTR [r15], xmm0
	mov	r15, QWORD PTR 216[rsp]
	cmp	QWORD PTR 232[rsp], 0
	je	.L55
	lea	rax, 400[r15]
	mov	r14, QWORD PTR 232[rsp]
	mov	QWORD PTR 32[rsp], rax
	jmp	.L56
	.p2align 4,,10
	.p2align 3
.L71:
	add	r15, 8
	add	r14, 16
	cmp	QWORD PTR 32[rsp], r15
	je	.L70
.L56:
	mov	rcx, rsi
	pxor	xmm7, xmm7
	call	rbx
	mov	r13, QWORD PTR 56[rsp]
	mov	rcx, rbp
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, QWORD PTR "timer_frequency"[rip]
	cvtsi2sd	xmm7, r13
	mulsd	xmm7, xmm6
	divsd	xmm7, xmm0
	call	r12
	mov	rcx, rsi
	mov	QWORD PTR [rdi], rax
	call	rbx
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, QWORD PTR 56[rsp]
	pxor	xmm1, xmm1
	cvtsi2sd	xmm1, QWORD PTR "timer_frequency"[rip]
	mulsd	xmm0, xmm6
	divsd	xmm0, xmm1
	subsd	xmm0, xmm7
	mulsd	xmm0, xmm6
	addsd	xmm0, xmm8
	cvttsd2si	rax, xmm0
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, rax
	divsd	xmm0, xmm6
	movabs	rax, 500000500000
	movsd	QWORD PTR [r15], xmm0
	movq	xmm0, r13
	movhps	xmm0, QWORD PTR 56[rsp]
	movups	XMMWORD PTR [r14], xmm0
	cmp	QWORD PTR [rdi], rax
	je	.L71
.L53:
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
.L69:
	mov	rbx, QWORD PTR __imp_QueryPerformanceCounter[rip]
	jmp	.L52
.L55:
	lea	r14, 400[r15]
	movabs	r13, 500000500000
	jmp	.L60
	.p2align 4,,10
	.p2align 3
.L58:
	add	r15, 8
	cmp	r15, r14
	je	.L61
.L60:
	mov	rcx, rsi
	pxor	xmm7, xmm7
	call	rbx
	cvtsi2sd	xmm7, QWORD PTR 56[rsp]
	mulsd	xmm7, xmm6
	mov	rcx, rbp
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, QWORD PTR "timer_frequency"[rip]
	divsd	xmm7, xmm0
	call	r12
	mov	rcx, rsi
	mov	QWORD PTR [rdi], rax
	call	rbx
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, QWORD PTR 56[rsp]
	pxor	xmm1, xmm1
	cvtsi2sd	xmm1, QWORD PTR "timer_frequency"[rip]
	mulsd	xmm0, xmm6
	divsd	xmm0, xmm1
	subsd	xmm0, xmm7
	mulsd	xmm0, xmm6
	addsd	xmm0, xmm8
	cvttsd2si	rax, xmm0
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, rax
	divsd	xmm0, xmm6
	movsd	QWORD PTR [r15], xmm0
	cmp	QWORD PTR [rdi], r13
	je	.L58
	jmp	.L53
.L70:
	mov	rcx, rsi
	call	rbx
	mov	rax, QWORD PTR 56[rsp]
	mov	rdx, QWORD PTR 232[rsp]
	mov	QWORD PTR 808[rdx], rax
.L61:
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
.LC31:
	.ascii "--diagnostic-trace=\0"
	.align 8
.LC32:
	.ascii "status=error\12message=diagnostic trace requires result path\12\0"
	.align 8
.LC33:
	.ascii "status=error\12message=high-resolution timer is unavailable\12\0"
	.align 2
.LC34:
	.ascii "n\0t\0d\0l\0l\0.\0d\0l\0l\0\0\0"
.LC35:
	.ascii "RtlGetVersion\0"
.LC36:
	.ascii "%lu.%lu.%lu\0"
	.align 8
.LC37:
	.ascii "status=error\12message=failed to get OS version via RtlGetVersion\12\0"
.LC38:
	.ascii "--experiment-id=\0"
.LC39:
	.ascii "LANGBENCH_EXPERIMENT_ID\0"
.LC40:
	.ascii "--run-id=\0"
.LC41:
	.ascii "LANGBENCH_RUN_ID\0"
.LC42:
	.ascii "%s_%s\0"
.LC43:
	.ascii "function_call_numeric_sum\0"
.LC44:
	.ascii "%s_%s_%s\0"
.LC45:
	.ascii "c\0"
	.align 8
.LC46:
	.ascii "status=error\12message=failed to allocate array\12\0"
	.align 8
.LC50:
	.ascii "status=error\12message=checksum mismatch\12\0"
	.align 8
.LC51:
	.ascii "status=error\12message=failed to get cwd\12\0"
	.align 8
.LC52:
	.ascii "status=error\12message=result path is too long\12\0"
	.align 8
.LC53:
	.ascii "results\\function_call_numeric_sum_c_result.json\0"
.LC54:
	.ascii "%Y-%m-%dT%H:%M:%S\0"
.LC55:
	.ascii "%s%c%02d:%02d\0"
	.align 8
.LC56:
	.ascii "HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0\0"
.LC57:
	.ascii "ProcessorNameString\0"
.LC58:
	.ascii "wb\0"
	.align 8
.LC59:
	.ascii "status=error\12message=failed to open result: %s\12\0"
	.align 8
.LC60:
	.ascii "{\12  \"type\": \"langbench_result\",\12  \"schema_version\": \"1.0\",\12  \"project\": \"LangBench Live\",\12  \"benchmark\": \"%s\",\12  \"experiment_id\": \0"
.LC61:
	.ascii ",\12  \"run_id\": \0"
	.align 8
.LC62:
	.ascii ",\12  \"language\": \"c\",\12  \"created_at\": \0"
	.align 8
.LC63:
	.ascii ",\12  \"status\": \"success\",\12  \"engine\": {\"runtime\": \"native\", \"runtime_version\": null},\12  \"execution\": {\"runner\": \"vscode_terminal_powershell\", \"runner_label\": \"VSCode Terminal / PowerShell\", \"cwd\": \0"
.LC64:
	.ascii ", \"argv\": [\0"
.LC65:
	.ascii ", \0"
.LC66:
	.ascii "], \"measurement_order\": [\0"
	.align 8
.LC67:
	.ascii "]},\12  \"environment\": {\"os\": \"Windows\", \"os_version\": \0"
.LC68:
	.ascii ", \"architecture\": \0"
.LC69:
	.ascii "null\0"
.LC70:
	.ascii ", \"cpu\": \0"
	.align 8
.LC71:
	.ascii ", \"logical_processors\": %lu, \"memory_bytes\": \0"
.LC72:
	.ascii "%llu\0"
	.align 8
.LC73:
	.ascii "},\12  \"build\": {\"required\": true, \"compiler\": \"gcc\", \"compiler_version\": \0"
.LC74:
	.ascii ", \"compile_command\": \0"
	.align 8
.LC75:
	.ascii ", \"compile_ms\": %.3f, \"source_path\": \0"
	.align 8
.LC76:
	.ascii "},\12  \"optimization_analysis\": \0"
.LC77:
	.ascii "rb\0"
.LC78:
	.ascii ",\12\0"
	.align 8
.LC79:
	.ascii "  \"config\": {\"item_count\": %d, \"warmup_iterations\": %d, \"measurement_iterations\": %d, \"numeric_type\": \"integer\", \"value_field\": \"value\", \"cases\": [\"direct\", \"function_call\"]},\12  \"timing\": {\"process_startup_ms\": null, \"setup_ms\": %.3f, \"warmup_ms\": %.3f, \"measurement_ms\": %.3f, \"benchmark_total_ms\": %.3f},\12  \"results\": {\"direct\": \0"
.LC80:
	.ascii ", \"function_call\": \0"
	.align 8
.LC81:
	.ascii "},\12  \"validation\": {\"direct_checksum\": %lld, \"function_call_checksum\": %lld, \"expected_checksum\": %lld, \"tolerance\": 0, \"passed\": true},\12  \"error\": null\12}\12\0"
	.align 8
.LC82:
	.ascii "status=error\12message=failed to read optimization analysis JSON\12\0"
	.align 8
.LC83:
	.ascii "status=error\12message=failed to finish writing result JSON\12\0"
	.align 8
.LC84:
	.ascii "{\"schema_version\":\"1.0\",\"clock\":\"windows_qpc\",\"frequency_hz\":%lld,\"anchor\":{\"filetime_100ns\":%llu,\"qpc_before\":%lld,\"qpc_after\":%lld},\"measurement_order\":[\"%s\",\"%s\"],\"cases\":{\0"
	.align 8
.LC85:
	.ascii "%s\"%s\":{\"start_qpc\":%lld,\"end_qpc\":%lld,\"samples\":[\0"
	.align 8
.LC86:
	.ascii "%s{\"number\":%d,\"start_qpc\":%lld,\"end_qpc\":%lld,\"sample_ms\":%.3f}\0"
.LC87:
	.ascii "]}\0"
.LC88:
	.ascii "}}\12\0"
	.align 8
.LC89:
	.ascii "status=error\12message=failed to write diagnostic trace\12\0"
.LC90:
	.ascii "status=success\0"
	.section	.text.startup,"x"
	.p2align 4
	.globl	"main"
	.def	"main";	.scl	2;	.type	32;	.endef
	.seh_proc	"main"
"main":
	push	r15
	.seh_pushreg	r15
	mov	eax, 24248
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
	.seh_stackalloc	24248
	movups	XMMWORD PTR 24176[rsp], xmm6
	.seh_savexmm	xmm6, 24176
	movups	XMMWORD PTR 24192[rsp], xmm7
	.seh_savexmm	xmm7, 24192
	movups	XMMWORD PTR 24208[rsp], xmm8
	.seh_savexmm	xmm8, 24208
	movups	XMMWORD PTR 24224[rsp], xmm9
	.seh_savexmm	xmm9, 24224
	.seh_endprologue
	mov	ebp, ecx
	mov	rbx, rdx
	call	"__main"
	pxor	xmm0, xmm0
	xor	edx, edx
	mov	r8d, 4096
	lea	rcx, 11888[rsp]
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
	mov	QWORD PTR 192[rsp], 0
	mov	QWORD PTR 200[rsp], 0
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
	movups	XMMWORD PTR 1184[rsp], xmm0
	movups	XMMWORD PTR 1200[rsp], xmm0
	movups	XMMWORD PTR 1216[rsp], xmm0
	movups	XMMWORD PTR 1232[rsp], xmm0
	movups	XMMWORD PTR 1248[rsp], xmm0
	movups	XMMWORD PTR 240[rsp], xmm0
	movups	XMMWORD PTR 256[rsp], xmm0
	call	"memset"
	xor	edx, edx
	mov	r8d, 4096
	lea	rcx, 15984[rsp]
	call	"memset"
	cmp	ebp, 5
	jle	.L73
	mov	rcx, QWORD PTR 8[rbx]
	lea	r8, 168[rsp]
	lea	rdx, .LC23[rip]
	call	"sscanf"
	mov	r10d, eax
	cmp	eax, 1
	je	.L198
.L73:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 72
	mov	edx, 1
	lea	rcx, .LC24[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, 1
.L72:
	movups	xmm6, XMMWORD PTR 24176[rsp]
	mov	eax, r10d
	movups	xmm7, XMMWORD PTR 24192[rsp]
	movups	xmm8, XMMWORD PTR 24208[rsp]
	movups	xmm9, XMMWORD PTR 24224[rsp]
	add	rsp, 24248
	pop	rbx
	pop	rsi
	pop	rdi
	pop	rbp
	pop	r12
	pop	r13
	pop	r14
	pop	r15
	ret
.L198:
	pxor	xmm0, xmm0
	comisd	xmm0, QWORD PTR 168[rsp]
	ja	.L73
	mov	rax, QWORD PTR 16[rbx]
	cmp	BYTE PTR [rax], 0
	je	.L73
	mov	rax, QWORD PTR 24[rbx]
	cmp	BYTE PTR [rax], 0
	je	.L73
	mov	rax, QWORD PTR 32[rbx]
	cmp	BYTE PTR [rax], 0
	je	.L73
	mov	rax, QWORD PTR 40[rbx]
	cmp	BYTE PTR [rax], 0
	je	.L73
	mov	QWORD PTR 32[rsp], 32
	lea	r9, 240[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	lea	r8, .LC25[rip]
	mov	DWORD PTR 88[rsp], r10d
	call	"optional_arg"
	lea	rdx, .LC26[rip]
	lea	rcx, 240[rsp]
	call	"strcmp"
	cmp	BYTE PTR 240[rsp], 0
	mov	r10d, DWORD PTR 88[rsp]
	mov	r14d, eax
	je	.L76
	test	eax, eax
	je	.L77
	lea	rdx, .LC27[rip]
	lea	rcx, 240[rsp]
	call	"strcmp"
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	jne	.L199
.L78:
	mov	QWORD PTR 32[rsp], 4096
	lea	r9, 11888[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	lea	r8, .LC29[rip]
	mov	DWORD PTR 88[rsp], r10d
	call	"optional_arg"
	mov	r10d, DWORD PTR 88[rsp]
	movzx	r15d, BYTE PTR 11888[rsp]
.L80:
	mov	QWORD PTR 32[rsp], 4096
	lea	r9, 15984[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	lea	r8, .LC31[rip]
	mov	DWORD PTR 88[rsp], r10d
	call	"optional_arg"
	cmp	BYTE PTR 15984[rsp], 0
	mov	r10d, DWORD PTR 88[rsp]
	je	.L82
	test	r15b, r15b
	je	.L200
.L82:
	mov	DWORD PTR 88[rsp], r10d
	lea	rcx, "timer_frequency"[rip]
	call	[QWORD PTR __imp_QueryPerformanceFrequency[rip]]
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	je	.L83
	cmp	QWORD PTR "timer_frequency"[rip], 0
	je	.L83
	mov	DWORD PTR 88[rsp], r10d
	lea	rcx, .LC34[rip]
	call	[QWORD PTR __imp_GetModuleHandleW[rip]]
	mov	r10d, DWORD PTR 88[rsp]
	test	rax, rax
	je	.L85
	lea	rdx, .LC35[rip]
	mov	rcx, rax
	call	[QWORD PTR __imp_GetProcAddress[rip]]
	mov	r10d, DWORD PTR 88[rsp]
	test	rax, rax
	je	.L85
	xor	edx, edx
	mov	r8d, 276
	mov	QWORD PTR 96[rsp], rax
	lea	rcx, 20080[rsp]
	call	"memset"
	lea	rcx, 20080[rsp]
	mov	DWORD PTR 20080[rsp], 276
	call	[QWORD PTR 96[rsp]]
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	je	.L201
.L85:
	mov	DWORD PTR 88[rsp], r10d
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 64
	mov	edx, 1
	lea	rcx, .LC37[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L72
.L76:
	test	eax, eax
	jne	.L78
.L77:
	mov	QWORD PTR 32[rsp], 4096
	lea	r9, 11888[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	lea	r8, .LC29[rip]
	mov	DWORD PTR 88[rsp], r10d
	call	"optional_arg"
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	je	.L79
	movzx	r15d, BYTE PTR 11888[rsp]
	jmp	.L80
.L83:
	mov	DWORD PTR 88[rsp], r10d
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 58
	mov	edx, 1
	lea	rcx, .LC33[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L72
.L201:
	mov	eax, DWORD PTR 20092[rsp]
	mov	r9d, DWORD PTR 20084[rsp]
	lea	r8, .LC36[rip]
	mov	edx, 64
	lea	rcx, 368[rsp]
	mov	DWORD PTR 40[rsp], eax
	mov	eax, DWORD PTR 20088[rsp]
	mov	DWORD PTR 32[rsp], eax
	call	"snprintf"
	cmp	BYTE PTR 15984[rsp], 0
	mov	r10d, DWORD PTR 88[rsp]
	jne	.L87
	xor	r8d, r8d
	mov	QWORD PTR 112[rsp], r8
	mov	QWORD PTR 104[rsp], r8
	mov	QWORD PTR 96[rsp], r8
.L88:
	mov	QWORD PTR 32[rsp], 256
	lea	r9, 496[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	lea	r8, .LC38[rip]
	mov	DWORD PTR 88[rsp], r10d
	call	"optional_arg"
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	je	.L202
.L89:
	mov	QWORD PTR 32[rsp], 256
	lea	r9, 752[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	lea	r8, .LC40[rip]
	mov	DWORD PTR 88[rsp], r10d
	call	"optional_arg"
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	je	.L203
.L90:
	cmp	BYTE PTR 496[rsp], 0
	je	.L204
.L91:
	cmp	BYTE PTR 752[rsp], 0
	je	.L205
.L92:
	mov	DWORD PTR 88[rsp], r10d
	call	"now_ms"
	mov	ecx, 4000000
	movapd	xmm6, xmm0
	call	"malloc"
	mov	r10d, DWORD PTR 88[rsp]
	test	rax, rax
	mov	r12, rax
	je	.L206
	movdqu	xmm0, XMMWORD PTR .LC16[rip]
	movdqu	xmm5, XMMWORD PTR .LC47[rip]
	lea	rdx, 4000000[rax]
	movdqu	xmm4, XMMWORD PTR .LC48[rip]
	movdqu	xmm3, XMMWORD PTR .LC49[rip]
	.p2align 6
	.p2align 4
	.p2align 3
.L94:
	movdqa	xmm2, xmm0
	movdqa	xmm1, xmm0
	paddq	xmm0, xmm3
	add	rax, 16
	paddq	xmm2, xmm5
	shufps	xmm1, xmm2, 136
	paddd	xmm1, xmm4
	movups	XMMWORD PTR -16[rax], xmm1
	cmp	rdx, rax
	jne	.L94
	mov	DWORD PTR 88[rsp], r10d
	call	"now_ms"
	test	r14d, r14d
	mov	r10d, DWORD PTR 88[rsp]
	movzx	eax, BYTE PTR 15984[rsp]
	movapd	xmm7, xmm0
	jne	.L95
	xor	r11d, r11d
	test	al, al
	lea	rax, 2880[rsp]
	mov	rcx, r12
	cmove	rax, r11
	lea	r9, 1664[rsp]
	lea	r8, 184[rsp]
	mov	DWORD PTR 120[rsp], r10d
	lea	rdx, "function_call_sum"[rip]
	mov	QWORD PTR 88[rsp], r9
	mov	QWORD PTR 40[rsp], rax
	lea	rax, 200[rsp]
	mov	QWORD PTR 32[rsp], rax
	call	"measure.constprop.0"
	mov	r10d, DWORD PTR 120[rsp]
	test	eax, eax
	je	.L97
	xor	r11d, r11d
	lea	rax, 2064[rsp]
	cmp	BYTE PTR 15984[rsp], 0
	cmove	rax, r11
	lea	r9, 1264[rsp]
	lea	r8, 176[rsp]
	mov	r13, r9
	lea	rdx, "direct_sum"[rip]
	mov	QWORD PTR 40[rsp], rax
	lea	rax, 192[rsp]
	mov	QWORD PTR 32[rsp], rax
.L197:
	mov	rcx, r12
	call	"measure.constprop.0"
	mov	r10d, DWORD PTR 120[rsp]
	test	eax, eax
	je	.L97
	mov	rcx, r13
	mov	DWORD PTR 120[rsp], r10d
	lea	rdx, 3696[rsp]
	call	"sample_total"
	mov	rcx, QWORD PTR 88[rsp]
	movapd	xmm8, xmm0
	call	"sample_total"
	mov	ecx, 4096
	movapd	xmm9, xmm0
	call	[QWORD PTR __imp_GetCurrentDirectoryA[rip]]
	mov	r10d, DWORD PTR 120[rsp]
	test	eax, eax
	je	.L207
	mov	DWORD PTR 120[rsp], r10d
	test	r15b, r15b
	je	.L208
	lea	rdx, 11888[rsp]
	lea	rcx, 7792[rsp]
	mov	BYTE PTR 11888[rsp], r15b
	call	"strcpy"
	mov	r10d, DWORD PTR 120[rsp]
	lea	r15, 7792[rsp]
.L105:
	xor	ecx, ecx
	mov	DWORD PTR 120[rsp], r10d
	call	_time64
	lea	rdx, 224[rsp]
	lea	rcx, 432[rsp]
	mov	QWORD PTR 224[rsp], rax
	call	_localtime64_s
	lea	r9, 432[rsp]
	lea	r8, .LC54[rip]
	mov	edx, 32
	lea	rcx, 320[rsp]
	call	"strftime"
	lea	rcx, 20080[rsp]
	call	[QWORD PTR __imp_GetTimeZoneInformation[rip]]
	mov	ecx, DWORD PTR 20080[rsp]
	mov	r10d, DWORD PTR 120[rsp]
	cmp	eax, 1
	je	.L209
	mov	edx, ecx
	add	ecx, DWORD PTR 20248[rsp]
	cmp	eax, 2
	cmovne	ecx, edx
.L107:
	mov	eax, ecx
	mov	r8d, 60
	mov	DWORD PTR 120[rsp], r10d
	neg	eax
	lea	r9, 320[rsp]
	cmovs	eax, ecx
	cdq
	idiv	r8d
	test	ecx, ecx
	lea	r8, .LC55[rip]
	setg	cl
	movzx	ecx, cl
	lea	ecx, 43[rcx+rcx]
	mov	DWORD PTR 32[rsp], ecx
	lea	rcx, 272[rsp]
	mov	DWORD PTR 48[rsp], edx
	mov	edx, 48
	mov	DWORD PTR 40[rsp], eax
	call	"snprintf"
	xor	edx, edx
	xor	ecx, ecx
	xor	r8d, r8d
	lea	rax, 20080[rsp]
	mov	QWORD PTR 20080[rsp], rdx
	mov	r9d, 131097
	lea	rdx, .LC56[rip]
	mov	DWORD PTR 432[rsp], ecx
	mov	rcx, -2147483646
	mov	DWORD PTR 164[rsp], 256
	mov	BYTE PTR 1008[rsp], 0
	mov	QWORD PTR 32[rsp], rax
	call	[QWORD PTR __imp_RegOpenKeyExA[rip]]
	mov	r10d, DWORD PTR 120[rsp]
	test	eax, eax
	je	.L210
.L109:
	mov	DWORD PTR 120[rsp], r10d
	lea	rcx, 320[rsp]
	call	[QWORD PTR __imp_GetNativeSystemInfo[rip]]
	lea	rcx, 432[rsp]
	mov	DWORD PTR 432[rsp], 64
	call	[QWORD PTR __imp_GlobalMemoryStatusEx[rip]]
	mov	r10d, DWORD PTR 120[rsp]
	test	eax, eax
	jne	.L110
	xor	eax, eax
	mov	QWORD PTR 440[rsp], rax
.L110:
	lea	rdx, .LC58[rip]
	mov	rcx, r15
	mov	DWORD PTR 120[rsp], r10d
	call	"fopen"
	mov	r10d, DWORD PTR 120[rsp]
	test	rax, rax
	mov	rsi, rax
	je	.L211
	lea	r8, .LC43[rip]
	mov	rcx, rax
	mov	DWORD PTR 120[rsp], r10d
	lea	edi, -1[rbp]
	lea	rdx, .LC60[rip]
	call	"fprintf"
	lea	rdx, 496[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 14
	mov	edx, 1
	lea	rcx, .LC61[rip]
	call	"fwrite"
	lea	rdx, 752[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 37
	mov	edx, 1
	lea	rcx, .LC62[rip]
	call	"fwrite"
	lea	rdx, 272[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 196
	mov	edx, 1
	lea	rcx, .LC63[rip]
	call	"fwrite"
	lea	rdx, 3696[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 11
	mov	edx, 1
	lea	rcx, .LC64[rip]
	call	"fwrite"
	mov	DWORD PTR 24320[rsp], ebp
	mov	r15d, DWORD PTR 120[rsp]
	xor	ebp, ebp
	jmp	.L113
.L212:
	mov	r9, rsi
	mov	edx, 1
	add	rbp, 1
	mov	r8d, 2
	lea	rcx, .LC65[rip]
	call	"fwrite"
	cmp	DWORD PTR 24320[rsp], ebp
	jle	.L112
.L113:
	mov	rdx, QWORD PTR [rbx+rbp*8]
	mov	rcx, rsi
	call	"write_json_string"
	cmp	rdi, rbp
	jne	.L212
.L112:
	mov	r9, rsi
	mov	r8d, 25
	mov	edx, 1
	mov	DWORD PTR 120[rsp], r15d
	lea	rcx, .LC66[rip]
	call	"fwrite"
	test	r14d, r14d
	mov	r10d, DWORD PTR 120[rsp]
	jne	.L213
	lea	rdx, .LC18[rip]
	mov	rcx, rsi
	mov	DWORD PTR 136[rsp], r10d
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	lea	rcx, .LC65[rip]
	call	"fwrite"
	lea	rax, .LC18[rip]
	mov	r10d, DWORD PTR 136[rsp]
	mov	QWORD PTR 128[rsp], rax
	mov	r14, rax
	lea	rax, .LC17[rip]
	mov	QWORD PTR 120[rsp], rax
	mov	r15, rax
.L139:
	mov	rdx, r15
	mov	rcx, rsi
	mov	DWORD PTR 136[rsp], r10d
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 53
	mov	edx, 1
	lea	rcx, .LC67[rip]
	call	"fwrite"
	lea	rdx, 368[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 18
	mov	edx, 1
	lea	rcx, .LC68[rip]
	call	"fwrite"
	movzx	eax, WORD PTR 320[rsp]
	mov	r10d, DWORD PTR 136[rsp]
	cmp	ax, 9
	je	.L146
	ja	.L117
	test	ax, ax
	je	.L147
	lea	rdx, .LC20[rip]
	cmp	ax, 5
	jne	.L118
.L116:
	mov	rcx, rsi
	mov	DWORD PTR 136[rsp], r10d
	call	"write_json_string"
	mov	r10d, DWORD PTR 136[rsp]
.L119:
	mov	r9, rsi
	mov	r8d, 9
	mov	edx, 1
	mov	DWORD PTR 136[rsp], r10d
	lea	rcx, .LC70[rip]
	call	"fwrite"
	cmp	BYTE PTR 1008[rsp], 0
	je	.L120
	lea	rdx, 1008[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r10d, DWORD PTR 136[rsp]
.L121:
	mov	r8d, DWORD PTR 352[rsp]
	lea	rdx, .LC71[rip]
	mov	rcx, rsi
	mov	DWORD PTR 136[rsp], r10d
	call	"fprintf"
	mov	r8, QWORD PTR 440[rsp]
	test	r8, r8
	je	.L122
	lea	rdx, .LC72[rip]
	mov	rcx, rsi
	call	"fprintf"
	mov	r10d, DWORD PTR 136[rsp]
.L123:
	mov	r9, rsi
	mov	r8d, 72
	mov	edx, 1
	mov	DWORD PTR 136[rsp], r10d
	lea	rcx, .LC73[rip]
	call	"fwrite"
	mov	rdx, QWORD PTR 16[rbx]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 21
	mov	edx, 1
	lea	rcx, .LC74[rip]
	call	"fwrite"
	mov	rdx, QWORD PTR 24[rbx]
	mov	rcx, rsi
	call	"write_json_string"
	lea	rdx, .LC75[rip]
	mov	rcx, rsi
	movsd	xmm2, QWORD PTR 168[rsp]
	movq	r8, xmm2
	call	"fprintf"
	mov	rdx, QWORD PTR 32[rbx]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 30
	mov	edx, 1
	lea	rcx, .LC76[rip]
	call	"fwrite"
	mov	rcx, QWORD PTR 40[rbx]
	lea	rdx, .LC77[rip]
	call	"fopen"
	mov	r10d, DWORD PTR 136[rsp]
	test	rax, rax
	mov	rbp, rax
	je	.L124
	mov	edi, r10d
	jmp	.L125
.L126:
	mov	r9, rsi
	mov	r8, rbx
	mov	edx, 1
	lea	rcx, 20080[rsp]
	call	"fwrite"
	cmp	rbx, rax
	jne	.L214
.L125:
	mov	r9, rbp
	mov	r8d, 4096
	mov	edx, 1
	lea	rcx, 20080[rsp]
	call	"fread"
	mov	rbx, rax
	test	rax, rax
	jne	.L126
	mov	rcx, rbp
	mov	DWORD PTR 136[rsp], edi
	call	"ferror"
	mov	r10d, DWORD PTR 136[rsp]
	test	eax, eax
	jne	.L215
	movapd	xmm0, xmm7
	pxor	xmm4, xmm4
	pxor	xmm5, xmm5
	mov	rcx, rbp
	subsd	xmm0, xmm6
	movsd	xmm2, QWORD PTR .LC1[rip]
	mov	DWORD PTR 156[rsp], r10d
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
	movsd	QWORD PTR 144[rsp], xmm4
	movsd	QWORD PTR 136[rsp], xmm5
	call	"fclose"
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	lea	rcx, .LC78[rip]
	call	"fwrite"
	movsd	xmm2, QWORD PTR .LC1[rip]
	mov	rcx, rsi
	movsd	xmm1, QWORD PTR 176[rsp]
	movsd	xmm4, QWORD PTR 144[rsp]
	mov	DWORD PTR 32[rsp], 50
	mov	r9d, 5
	mov	r8d, 1000000
	movapd	xmm0, xmm1
	lea	rdx, .LC79[rip]
	movsd	xmm3, QWORD PTR 184[rsp]
	movsd	xmm5, QWORD PTR 136[rsp]
	addsd	xmm0, xmm4
	movsd	QWORD PTR 40[rsp], xmm4
	addsd	xmm1, xmm3
	movsd	QWORD PTR 56[rsp], xmm5
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
	lea	rcx, .LC80[rip]
	call	"fwrite"
	mov	rdx, QWORD PTR 88[rsp]
	mov	rcx, rsi
	call	"write_case"
	mov	r9, QWORD PTR 200[rsp]
	mov	r8, QWORD PTR 192[rsp]
	mov	rcx, rsi
	movabs	rax, 500000500000
	lea	rdx, .LC81[rip]
	mov	QWORD PTR 32[rsp], rax
	call	"fprintf"
	mov	rcx, rsi
	call	"ferror"
	mov	rcx, rsi
	mov	ebx, eax
	call	"fclose"
	mov	r10d, DWORD PTR 156[rsp]
	or	eax, ebx
	je	.L216
	mov	rcx, r12
	mov	DWORD PTR 88[rsp], r10d
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 58
	mov	edx, 1
	lea	rcx, .LC83[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L72
.L79:
	mov	DWORD PTR 88[rsp], r10d
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 67
	mov	edx, 1
	lea	rcx, .LC30[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L72
.L97:
	mov	rcx, r12
	mov	DWORD PTR 88[rsp], r10d
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 39
	mov	edx, 1
	lea	rcx, .LC50[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L72
.L200:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 59
	mov	edx, 1
	lea	rcx, .LC32[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L72
.L95:
	xor	r11d, r11d
	test	al, al
	lea	rax, 2064[rsp]
	mov	rcx, r12
	cmove	rax, r11
	lea	r9, 1264[rsp]
	lea	r8, 176[rsp]
	mov	DWORD PTR 88[rsp], r10d
	lea	rdx, "direct_sum"[rip]
	mov	r13, r9
	mov	QWORD PTR 40[rsp], rax
	lea	rax, 192[rsp]
	mov	QWORD PTR 32[rsp], rax
	call	"measure.constprop.0"
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	je	.L97
	xor	r11d, r11d
	lea	rax, 2880[rsp]
	mov	DWORD PTR 120[rsp], r10d
	cmp	BYTE PTR 15984[rsp], 0
	cmove	rax, r11
	lea	r9, 1664[rsp]
	lea	r8, 184[rsp]
	mov	QWORD PTR 88[rsp], r9
	lea	rdx, "function_call_sum"[rip]
	mov	QWORD PTR 40[rsp], rax
	lea	rax, 200[rsp]
	mov	QWORD PTR 32[rsp], rax
	jmp	.L197
.L205:
	lea	rcx, 20080[rsp]
	mov	DWORD PTR 88[rsp], r10d
	call	"timestamp_id.constprop.0"
	lea	rax, .LC43[rip]
	mov	edx, 256
	lea	r9, 20080[rsp]
	mov	QWORD PTR 40[rsp], rax
	lea	rax, .LC45[rip]
	lea	r8, .LC44[rip]
	mov	QWORD PTR 32[rsp], rax
	lea	rcx, 752[rsp]
	call	"snprintf"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L92
.L204:
	lea	rcx, 20080[rsp]
	mov	DWORD PTR 88[rsp], r10d
	call	"timestamp_id.constprop.0"
	lea	rax, .LC43[rip]
	mov	edx, 256
	lea	r9, 20080[rsp]
	mov	QWORD PTR 32[rsp], rax
	lea	r8, .LC42[rip]
	lea	rcx, 496[rsp]
	call	"snprintf"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L91
.L203:
	lea	rcx, .LC41[rip]
	call	"getenv"
	mov	r10d, DWORD PTR 88[rsp]
	test	rax, rax
	je	.L90
	mov	r8d, 255
	mov	rdx, rax
	lea	rcx, 752[rsp]
	call	"strncpy"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L90
.L202:
	lea	rcx, .LC39[rip]
	call	"getenv"
	mov	r10d, DWORD PTR 88[rsp]
	test	rax, rax
	je	.L89
	mov	r8d, 255
	mov	rdx, rax
	lea	rcx, 496[rsp]
	call	"strncpy"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L89
.L87:
	mov	rdx, QWORD PTR __imp_QueryPerformanceCounter[rip]
	mov	DWORD PTR 120[rsp], r10d
	lea	rcx, 20080[rsp]
	mov	QWORD PTR 88[rsp], rdx
	call	rdx
	mov	rax, QWORD PTR 20080[rsp]
	lea	rcx, 20080[rsp]
	mov	QWORD PTR 104[rsp], rax
	call	[QWORD PTR __imp_GetSystemTimePreciseAsFileTime[rip]]
	mov	rax, QWORD PTR 20080[rsp]
	lea	rcx, 20080[rsp]
	mov	QWORD PTR 96[rsp], rax
	call	[QWORD PTR 88[rsp]]
	mov	rax, QWORD PTR 20080[rsp]
	mov	r10d, DWORD PTR 120[rsp]
	mov	QWORD PTR 112[rsp], rax
	jmp	.L88
.L199:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 47
	mov	edx, 1
	lea	rcx, .LC28[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L72
.L208:
	lea	rcx, 3696[rsp]
	call	"strlen"
	mov	r10d, DWORD PTR 120[rsp]
	mov	r8, rax
	lea	rax, 49[rax]
	cmp	rax, 4096
	ja	.L217
	lea	rcx, 7792[rsp]
	lea	rdx, 3696[rsp]
	mov	DWORD PTR 128[rsp], r10d
	mov	QWORD PTR 120[rsp], r8
	lea	rsi, .LC53[rip]
	lea	r15, 7792[rsp]
	call	"memcpy"
	mov	r8, QWORD PTR 120[rsp]
	mov	ecx, DWORD PTR .LC53[rip+44]
	lea	rdi, 7793[rsp+r8]
	mov	DWORD PTR 7837[rsp+r8], ecx
	mov	ecx, 11
	mov	BYTE PTR 7792[rsp+r8], 92
	rep movsd
	mov	r10d, DWORD PTR 128[rsp]
	jmp	.L105
.L122:
	mov	r9, rsi
	mov	r8d, 4
	mov	edx, 1
	lea	rcx, .LC69[rip]
	call	"fwrite"
	mov	r10d, DWORD PTR 136[rsp]
	jmp	.L123
.L213:
	lea	rdx, .LC17[rip]
	mov	rcx, rsi
	mov	DWORD PTR 136[rsp], r10d
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	lea	rcx, .LC65[rip]
	call	"fwrite"
	lea	rax, .LC17[rip]
	mov	r10d, DWORD PTR 136[rsp]
	mov	QWORD PTR 120[rsp], rax
	mov	r14, rax
	lea	rax, .LC18[rip]
	mov	QWORD PTR 128[rsp], rax
	mov	r15, rax
	jmp	.L139
.L120:
	mov	r9, rsi
	mov	r8d, 4
	mov	edx, 1
	lea	rcx, .LC69[rip]
	call	"fwrite"
	mov	r10d, DWORD PTR 136[rsp]
	jmp	.L121
.L214:
	mov	rcx, rbp
	mov	DWORD PTR 88[rsp], edi
	call	"fclose"
	mov	r10d, DWORD PTR 88[rsp]
.L124:
	mov	rcx, rsi
	mov	DWORD PTR 88[rsp], r10d
	call	"fclose"
	mov	rcx, r12
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 63
	mov	edx, 1
	lea	rcx, .LC82[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L72
.L209:
	add	ecx, DWORD PTR 20164[rsp]
	jmp	.L107
.L210:
	lea	rax, 164[rsp]
	mov	rcx, QWORD PTR 20080[rsp]
	xor	r8d, r8d
	lea	r9, 432[rsp]
	mov	QWORD PTR 40[rsp], rax
	lea	rax, 1008[rsp]
	lea	rdx, .LC57[rip]
	mov	QWORD PTR 32[rsp], rax
	call	[QWORD PTR __imp_RegQueryValueExA[rip]]
	mov	rcx, QWORD PTR 20080[rsp]
	call	[QWORD PTR __imp_RegCloseKey[rip]]
	mov	r10d, DWORD PTR 120[rsp]
	jmp	.L109
.L207:
	mov	rcx, r12
	mov	DWORD PTR 88[rsp], r10d
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 39
	mov	edx, 1
	lea	rcx, .LC51[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L72
.L117:
	lea	rdx, .LC22[rip]
	cmp	ax, 12
	je	.L116
.L118:
	mov	r9, rsi
	mov	r8d, 4
	mov	edx, 1
	mov	DWORD PTR 136[rsp], r10d
	lea	rcx, .LC69[rip]
	call	"fwrite"
	mov	r10d, DWORD PTR 136[rsp]
	jmp	.L119
.L216:
	mov	rcx, r12
	mov	DWORD PTR 136[rsp], r10d
	call	"free"
	cmp	BYTE PTR 15984[rsp], 0
	je	.L130
	lea	rax, 2064[rsp]
	lea	rcx, 15984[rsp]
	mov	QWORD PTR 224[rsp], r13
	mov	QWORD PTR 208[rsp], rax
	lea	rax, 2880[rsp]
	lea	rdx, .LC58[rip]
	mov	QWORD PTR 216[rsp], rax
	mov	rax, QWORD PTR 88[rsp]
	mov	QWORD PTR 232[rsp], rax
	mov	rax, QWORD PTR 120[rsp]
	mov	QWORD PTR 20080[rsp], rax
	mov	rax, QWORD PTR 128[rsp]
	mov	QWORD PTR 20088[rsp], rax
	call	"fopen"
	mov	r10d, DWORD PTR 136[rsp]
	test	rax, rax
	mov	rcx, rax
	mov	rdi, rax
	je	.L132
	mov	rax, QWORD PTR 112[rsp]
	mov	r9, QWORD PTR 96[rsp]
	mov	QWORD PTR 56[rsp], r15
	lea	rdx, .LC84[rip]
	mov	QWORD PTR 48[rsp], r14
	mov	r8, QWORD PTR "timer_frequency"[rip]
	mov	QWORD PTR 40[rsp], rax
	mov	rax, QWORD PTR 104[rsp]
	mov	DWORD PTR 88[rsp], r10d
	mov	QWORD PTR 32[rsp], rax
	call	"fprintf"
	mov	esi, DWORD PTR 88[rsp]
	xor	r10d, r10d
.L137:
	mov	rbx, QWORD PTR 208[rsp+r10*8]
	test	r10, r10
	mov	rcx, rdi
	mov	r9, QWORD PTR 20080[rsp+r10*8]
	lea	r8, .LC10[rip]
	mov	QWORD PTR 88[rsp], r10
	mov	rdx, QWORD PTR 808[rbx]
	mov	rax, QWORD PTR 800[rbx]
	mov	QWORD PTR 40[rsp], rdx
	lea	rdx, .LC85[rip]
	mov	QWORD PTR 32[rsp], rax
	lea	rax, .LC14[rip]
	cmove	r8, rax
	xor	ebp, ebp
	call	"fprintf"
	mov	r10, QWORD PTR 88[rsp]
.L136:
	mov	rax, QWORD PTR 224[rsp+r10*8]
	mov	rdx, QWORD PTR 8[rbx]
	mov	QWORD PTR 88[rsp], r10
	lea	r9d, 1[rbp]
	movsd	xmm0, QWORD PTR [rax+rbp*8]
	mov	rax, QWORD PTR [rbx]
	mov	QWORD PTR 40[rsp], rdx
	mov	QWORD PTR 32[rsp], rax
	movsd	QWORD PTR 48[rsp], xmm0
	test	ebp, ebp
	je	.L134
	lea	r8, .LC10[rip]
	lea	rdx, .LC86[rip]
	mov	rcx, rdi
	add	rbp, 1
	call	"fprintf"
	cmp	rbp, 50
	mov	r10, QWORD PTR 88[rsp]
	je	.L135
	add	rbx, 16
	jmp	.L136
.L134:
	mov	r9d, 1
	mov	rcx, rdi
	add	rbp, 1
	add	rbx, 16
	lea	r8, .LC14[rip]
	lea	rdx, .LC86[rip]
	call	"fprintf"
	mov	r10, QWORD PTR 88[rsp]
	jmp	.L136
.L218:
	test	ebp, ebp
	jne	.L132
.L130:
	lea	rcx, .LC90[rip]
	call	"puts"
	xor	r10d, r10d
	jmp	.L72
.L135:
	mov	r9, rdi
	mov	r8d, 2
	mov	edx, 1
	mov	QWORD PTR 88[rsp], r10
	lea	rcx, .LC87[rip]
	call	"fwrite"
	cmp	QWORD PTR 88[rsp], 1
	jne	.L151
	mov	r9, rdi
	mov	edx, 1
	mov	DWORD PTR 88[rsp], esi
	mov	r8d, 3
	lea	rcx, .LC88[rip]
	call	"fwrite"
	mov	rcx, rdi
	call	"ferror"
	mov	rcx, rdi
	mov	ebp, eax
	call	"fclose"
	mov	r10d, DWORD PTR 88[rsp]
	test	eax, eax
	je	.L218
.L132:
	mov	DWORD PTR 88[rsp], r10d
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 54
	mov	edx, 1
	lea	rcx, .LC89[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L72
.L211:
	mov	rcx, r12
	mov	DWORD PTR 88[rsp], r10d
	call	"free"
	call	[QWORD PTR __imp__errno[rip]]
	mov	ecx, DWORD PTR [rax]
	call	[QWORD PTR __imp_strerror[rip]]
	mov	ecx, 2
	mov	rbx, rax
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8, rbx
	lea	rdx, .LC59[rip]
	mov	rcx, rax
	call	"fprintf"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L72
.L146:
	lea	rdx, .LC19[rip]
	jmp	.L116
.L147:
	lea	rdx, .LC21[rip]
	jmp	.L116
.L215:
	mov	rcx, rbp
	mov	DWORD PTR 88[rsp], r10d
	call	"fclose"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L124
.L217:
	mov	rcx, r12
	mov	DWORD PTR 88[rsp], r10d
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 45
	mov	edx, 1
	lea	rcx, .LC52[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L72
.L151:
	mov	r10d, 1
	jmp	.L137
.L206:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 46
	mov	edx, 1
	lea	rcx, .LC46[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r10d, DWORD PTR 88[rsp]
	jmp	.L72
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
.LC47:
	.quad	2
	.quad	2
	.align 16
.LC48:
	.long	1
	.long	1
	.long	1
	.long	1
	.align 16
.LC49:
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

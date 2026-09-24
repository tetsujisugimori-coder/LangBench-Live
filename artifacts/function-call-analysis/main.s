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
.LC16:
	.ascii "direct\0"
.LC17:
	.ascii "function_call\0"
.LC18:
	.ascii "x64\0"
.LC19:
	.ascii "arm\0"
.LC20:
	.ascii "x86\0"
.LC21:
	.ascii "arm64\0"
.LC22:
	.ascii "%lf\0"
	.align 8
.LC23:
	.ascii "status=error\12message=expected build and optimization analysis arguments\12\0"
.LC24:
	.ascii "--measurement-order=\0"
.LC25:
	.ascii "function_call_first\0"
.LC26:
	.ascii "direct_first\0"
	.align 8
.LC27:
	.ascii "status=error\12message=invalid measurement order\12\0"
.LC28:
	.ascii "--result-path=\0"
	.align 8
.LC29:
	.ascii "status=error\12message=reverse order requires diagnostic result path\12\0"
.LC30:
	.ascii "--diagnostic-trace=\0"
	.align 8
.LC31:
	.ascii "status=error\12message=diagnostic trace requires result path\12\0"
.LC32:
	.ascii "--diagnostic-affinity=\0"
	.align 8
.LC33:
	.ascii "status=error\12message=invalid logical CPU number: empty\12\0"
	.align 8
.LC34:
	.ascii "status=error\12message=invalid logical CPU number: %s\12\0"
	.align 8
.LC35:
	.ascii "status=error\12message=GetProcessAffinityMask failed: %lu\12\0"
	.align 8
.LC36:
	.ascii "status=error\12message=logical CPU %lu is outside the process allowed affinity mask\12\0"
	.align 8
.LC37:
	.ascii "status=error\12message=SetProcessAffinityMask failed for logical CPU %lu: %lu\12\0"
	.align 8
.LC38:
	.ascii "status=error\12message=logical CPU %lu affinity verification failed\12\0"
	.align 8
.LC39:
	.ascii "status=error\12message=diagnostic affinity requires result path\12\0"
	.align 8
.LC40:
	.ascii "status=error\12message=high-resolution timer is unavailable\12\0"
	.align 2
.LC41:
	.ascii "n\0t\0d\0l\0l\0.\0d\0l\0l\0\0\0"
.LC42:
	.ascii "RtlGetVersion\0"
.LC43:
	.ascii "%lu.%lu.%lu\0"
	.align 8
.LC44:
	.ascii "status=error\12message=failed to get OS version via RtlGetVersion\12\0"
.LC45:
	.ascii "--experiment-id=\0"
.LC46:
	.ascii "LANGBENCH_EXPERIMENT_ID\0"
.LC47:
	.ascii "--run-id=\0"
.LC48:
	.ascii "LANGBENCH_RUN_ID\0"
.LC49:
	.ascii "%s_%s\0"
.LC50:
	.ascii "function_call_numeric_sum\0"
.LC51:
	.ascii "%s_%s_%s\0"
.LC52:
	.ascii "c\0"
	.align 8
.LC53:
	.ascii "status=error\12message=failed to allocate array\12\0"
	.align 8
.LC54:
	.ascii "status=error\12message=checksum mismatch\12\0"
	.align 8
.LC55:
	.ascii "status=error\12message=failed to get cwd\12\0"
	.align 8
.LC56:
	.ascii "status=error\12message=result path is too long\12\0"
	.align 8
.LC57:
	.ascii "results\\function_call_numeric_sum_c_result.json\0"
.LC58:
	.ascii "%Y-%m-%dT%H:%M:%S\0"
.LC59:
	.ascii "%s%c%02d:%02d\0"
	.align 8
.LC60:
	.ascii "HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0\0"
.LC61:
	.ascii "ProcessorNameString\0"
.LC62:
	.ascii "wb\0"
	.align 8
.LC63:
	.ascii "status=error\12message=failed to open result: %s\12\0"
	.align 8
.LC64:
	.ascii "{\12  \"type\": \"langbench_result\",\12  \"schema_version\": \"1.0\",\12  \"project\": \"LangBench Live\",\12  \"benchmark\": \"%s\",\12  \"experiment_id\": \0"
.LC65:
	.ascii ",\12  \"run_id\": \0"
	.align 8
.LC66:
	.ascii ",\12  \"language\": \"c\",\12  \"created_at\": \0"
	.align 8
.LC67:
	.ascii ",\12  \"status\": \"success\",\12  \"engine\": {\"runtime\": \"native\", \"runtime_version\": null},\12  \"execution\": {\"runner\": \"vscode_terminal_powershell\", \"runner_label\": \"VSCode Terminal / PowerShell\", \"cwd\": \0"
.LC68:
	.ascii ", \"argv\": [\0"
.LC69:
	.ascii ", \0"
.LC70:
	.ascii "], \"measurement_order\": [\0"
	.align 8
.LC71:
	.ascii "]},\12  \"environment\": {\"os\": \"Windows\", \"os_version\": \0"
.LC72:
	.ascii ", \"architecture\": \0"
.LC73:
	.ascii "null\0"
.LC74:
	.ascii ", \"cpu\": \0"
	.align 8
.LC75:
	.ascii ", \"logical_processors\": %lu, \"memory_bytes\": \0"
.LC76:
	.ascii "%llu\0"
	.align 8
.LC77:
	.ascii "},\12  \"build\": {\"required\": true, \"compiler\": \"gcc\", \"compiler_version\": \0"
.LC78:
	.ascii ", \"compile_command\": \0"
	.align 8
.LC79:
	.ascii ", \"compile_ms\": %.3f, \"source_path\": \0"
	.align 8
.LC80:
	.ascii "},\12  \"optimization_analysis\": \0"
.LC81:
	.ascii "rb\0"
.LC82:
	.ascii ",\12\0"
	.align 8
.LC83:
	.ascii "  \"config\": {\"item_count\": %d, \"warmup_iterations\": %d, \"measurement_iterations\": %d, \"numeric_type\": \"integer\", \"value_field\": \"value\", \"cases\": [\"direct\", \"function_call\"]},\12  \"timing\": {\"process_startup_ms\": null, \"setup_ms\": %.3f, \"warmup_ms\": %.3f, \"measurement_ms\": %.3f, \"benchmark_total_ms\": %.3f},\12  \"results\": {\"direct\": \0"
.LC84:
	.ascii ", \"function_call\": \0"
	.align 8
.LC85:
	.ascii "},\12  \"validation\": {\"direct_checksum\": %lld, \"function_call_checksum\": %lld, \"expected_checksum\": %lld, \"tolerance\": 0, \"passed\": true},\12  \"error\": null\12}\12\0"
	.align 8
.LC86:
	.ascii "status=error\12message=failed to read optimization analysis JSON\12\0"
	.align 8
.LC87:
	.ascii "status=error\12message=failed to finish writing result JSON\12\0"
	.align 8
.LC88:
	.ascii "{\"schema_version\":\"1.0\",\"clock\":\"windows_qpc\",\"frequency_hz\":%lld,\"anchor\":{\"filetime_100ns\":%llu,\"qpc_before\":%lld,\"qpc_after\":%lld},\"measurement_order\":[\"%s\",\"%s\"],\"cases\":{\0"
	.align 8
.LC89:
	.ascii "%s\"%s\":{\"start_qpc\":%lld,\"end_qpc\":%lld,\"samples\":[\0"
	.align 8
.LC90:
	.ascii "%s{\"number\":%d,\"start_qpc\":%lld,\"end_qpc\":%lld,\"sample_ms\":%.3f}\0"
.LC91:
	.ascii "]}\0"
.LC92:
	.ascii "}}\12\0"
	.align 8
.LC93:
	.ascii "status=error\12message=failed to write diagnostic trace\12\0"
.LC94:
	.ascii "status=success\0"
	.section	.text.startup,"x"
	.p2align 4
	.globl	"main"
	.def	"main";	.scl	2;	.type	32;	.endef
	.seh_proc	"main"
"main":
	push	r15
	.seh_pushreg	r15
	mov	eax, 24296
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
	.seh_stackalloc	24296
	movups	XMMWORD PTR 24224[rsp], xmm6
	.seh_savexmm	xmm6, 24224
	movups	XMMWORD PTR 24240[rsp], xmm7
	.seh_savexmm	xmm7, 24240
	movups	XMMWORD PTR 24256[rsp], xmm8
	.seh_savexmm	xmm8, 24256
	movups	XMMWORD PTR 24272[rsp], xmm9
	.seh_savexmm	xmm9, 24272
	.seh_endprologue
	pxor	xmm6, xmm6
	mov	ebp, ecx
	mov	rbx, rdx
	call	"__main"
	mov	r8d, 4096
	xor	edx, edx
	lea	rcx, 11936[rsp]
	mov	QWORD PTR 176[rsp], 0
	mov	QWORD PTR 184[rsp], 0
	movups	XMMWORD PTR 544[rsp], xmm6
	movups	XMMWORD PTR 560[rsp], xmm6
	movups	XMMWORD PTR 576[rsp], xmm6
	movups	XMMWORD PTR 592[rsp], xmm6
	movups	XMMWORD PTR 608[rsp], xmm6
	movups	XMMWORD PTR 624[rsp], xmm6
	movups	XMMWORD PTR 640[rsp], xmm6
	movups	XMMWORD PTR 656[rsp], xmm6
	movups	XMMWORD PTR 672[rsp], xmm6
	movups	XMMWORD PTR 688[rsp], xmm6
	movups	XMMWORD PTR 704[rsp], xmm6
	movups	XMMWORD PTR 720[rsp], xmm6
	movups	XMMWORD PTR 736[rsp], xmm6
	movups	XMMWORD PTR 752[rsp], xmm6
	movups	XMMWORD PTR 768[rsp], xmm6
	movups	XMMWORD PTR 784[rsp], xmm6
	movups	XMMWORD PTR 800[rsp], xmm6
	movups	XMMWORD PTR 816[rsp], xmm6
	movups	XMMWORD PTR 832[rsp], xmm6
	movups	XMMWORD PTR 848[rsp], xmm6
	movups	XMMWORD PTR 864[rsp], xmm6
	movups	XMMWORD PTR 880[rsp], xmm6
	movups	XMMWORD PTR 896[rsp], xmm6
	movups	XMMWORD PTR 912[rsp], xmm6
	movups	XMMWORD PTR 928[rsp], xmm6
	movups	XMMWORD PTR 944[rsp], xmm6
	movups	XMMWORD PTR 960[rsp], xmm6
	movups	XMMWORD PTR 976[rsp], xmm6
	movups	XMMWORD PTR 992[rsp], xmm6
	movups	XMMWORD PTR 1008[rsp], xmm6
	movups	XMMWORD PTR 1024[rsp], xmm6
	movups	XMMWORD PTR 1040[rsp], xmm6
	movups	XMMWORD PTR 1056[rsp], xmm6
	movups	XMMWORD PTR 1072[rsp], xmm6
	movups	XMMWORD PTR 1088[rsp], xmm6
	movups	XMMWORD PTR 1104[rsp], xmm6
	movups	XMMWORD PTR 1120[rsp], xmm6
	movups	XMMWORD PTR 1136[rsp], xmm6
	movups	XMMWORD PTR 1152[rsp], xmm6
	movups	XMMWORD PTR 1168[rsp], xmm6
	movups	XMMWORD PTR 1184[rsp], xmm6
	movups	XMMWORD PTR 1200[rsp], xmm6
	movups	XMMWORD PTR 1216[rsp], xmm6
	movups	XMMWORD PTR 1232[rsp], xmm6
	movups	XMMWORD PTR 1248[rsp], xmm6
	movups	XMMWORD PTR 1264[rsp], xmm6
	movups	XMMWORD PTR 1280[rsp], xmm6
	movups	XMMWORD PTR 1296[rsp], xmm6
	movups	XMMWORD PTR 224[rsp], xmm6
	movups	XMMWORD PTR 240[rsp], xmm6
	call	"memset"
	mov	r8d, 4096
	xor	edx, edx
	lea	rcx, 16032[rsp]
	call	"memset"
	movups	XMMWORD PTR 480[rsp], xmm6
	movups	XMMWORD PTR 496[rsp], xmm6
	movups	XMMWORD PTR 512[rsp], xmm6
	movups	XMMWORD PTR 528[rsp], xmm6
	cmp	ebp, 5
	jle	.L73
	mov	rcx, QWORD PTR 8[rbx]
	lea	r8, 152[rsp]
	lea	rdx, .LC22[rip]
	call	"sscanf"
	sub	eax, 1
	je	.L220
.L73:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 72
	mov	edx, 1
	lea	rcx, .LC23[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r11d, 1
.L72:
	movups	xmm6, XMMWORD PTR 24224[rsp]
	mov	eax, r11d
	movups	xmm7, XMMWORD PTR 24240[rsp]
	movups	xmm8, XMMWORD PTR 24256[rsp]
	movups	xmm9, XMMWORD PTR 24272[rsp]
	add	rsp, 24296
	pop	rbx
	pop	rsi
	pop	rdi
	pop	rbp
	pop	r12
	pop	r13
	pop	r14
	pop	r15
	ret
.L220:
	pxor	xmm0, xmm0
	comisd	xmm0, QWORD PTR 152[rsp]
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
	lea	r9, 224[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	lea	r8, .LC24[rip]
	call	"optional_arg"
	lea	rdx, .LC25[rip]
	lea	rcx, 224[rsp]
	call	"strcmp"
	mov	r14d, eax
	cmp	BYTE PTR 224[rsp], 0
	je	.L76
	test	eax, eax
	je	.L77
	lea	rdx, .LC26[rip]
	lea	rcx, 224[rsp]
	call	"strcmp"
	test	eax, eax
	jne	.L221
.L78:
	mov	QWORD PTR 32[rsp], 4096
	lea	r9, 11936[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	lea	r8, .LC28[rip]
	call	"optional_arg"
.L217:
	mov	QWORD PTR 32[rsp], 4096
	lea	r9, 16032[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	movzx	r15d, BYTE PTR 11936[rsp]
	lea	r8, .LC30[rip]
	call	"optional_arg"
	cmp	BYTE PTR 16032[rsp], 0
	je	.L82
	test	r15b, r15b
	je	.L222
	mov	QWORD PTR 32[rsp], 64
	lea	r9, 480[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	lea	r8, .LC32[rip]
	lea	rdi, 480[rsp]
	call	"optional_arg"
	test	eax, eax
	je	.L84
.L151:
	cmp	BYTE PTR 480[rsp], 0
	je	.L223
	mov	r9, QWORD PTR __imp__errno[rip]
	mov	QWORD PTR 80[rsp], r9
	call	r9
	xor	r9d, r9d
	mov	r8d, 10
	mov	rcx, rdi
	mov	DWORD PTR [rax], r9d
	lea	rdx, 3744[rsp]
	call	"strtoul"
	mov	esi, eax
	call	[QWORD PTR 80[rsp]]
	cmp	DWORD PTR [rax], 0
	jne	.L87
	mov	rax, QWORD PTR 3744[rsp]
	cmp	rax, rdi
	je	.L87
	cmp	BYTE PTR [rax], 0
	jne	.L87
	cmp	esi, 63
	ja	.L87
	mov	r9, QWORD PTR __imp_GetCurrentProcess[rip]
	mov	QWORD PTR 80[rsp], r9
	call	r9
	lea	r8, 20128[rsp]
	lea	rdx, 7840[rsp]
	mov	rcx, rax
	mov	rax, QWORD PTR __imp_GetProcessAffinityMask[rip]
	mov	r12, rax
	call	rax
	mov	r9, QWORD PTR 80[rsp]
	test	eax, eax
	je	.L224
	mov	eax, 1
	mov	ecx, esi
	sal	rax, cl
	mov	rdi, rax
	test	QWORD PTR 7840[rsp], rax
	je	.L225
	mov	QWORD PTR 80[rsp], r9
	call	r9
	mov	rdx, rdi
	mov	rcx, rax
	call	[QWORD PTR __imp_SetProcessAffinityMask[rip]]
	test	eax, eax
	je	.L226
	call	[QWORD PTR 80[rsp]]
	lea	r8, 20128[rsp]
	lea	rdx, 7840[rsp]
	mov	rcx, rax
	call	r12
	test	eax, eax
	je	.L93
	cmp	rdi, QWORD PTR 7840[rsp]
	je	.L84
.L93:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, esi
	lea	rdx, .LC38[rip]
	mov	rcx, rax
	call	"fprintf"
.L81:
	mov	r11d, 1
	jmp	.L72
.L76:
	test	eax, eax
	jne	.L78
.L77:
	mov	QWORD PTR 32[rsp], 4096
	lea	r9, 11936[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	lea	r8, .LC28[rip]
	call	"optional_arg"
	test	eax, eax
	jne	.L217
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 67
	mov	edx, 1
	lea	rcx, .LC29[rip]
	mov	r9, rax
	call	"fwrite"
	jmp	.L81
.L84:
	lea	rcx, "timer_frequency"[rip]
	call	[QWORD PTR __imp_QueryPerformanceFrequency[rip]]
	test	eax, eax
	je	.L95
	cmp	QWORD PTR "timer_frequency"[rip], 0
	je	.L95
	lea	rcx, .LC41[rip]
	call	[QWORD PTR __imp_GetModuleHandleW[rip]]
	test	rax, rax
	je	.L97
	lea	rdx, .LC42[rip]
	mov	rcx, rax
	call	[QWORD PTR __imp_GetProcAddress[rip]]
	test	rax, rax
	je	.L97
	xor	edx, edx
	mov	r8d, 276
	mov	QWORD PTR 80[rsp], rax
	lea	rcx, 20128[rsp]
	call	"memset"
	lea	rcx, 20128[rsp]
	mov	DWORD PTR 20128[rsp], 276
	call	[QWORD PTR 80[rsp]]
	test	eax, eax
	je	.L227
.L97:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 64
	mov	edx, 1
	lea	rcx, .LC44[rip]
	mov	r9, rax
	call	"fwrite"
	jmp	.L81
.L82:
	mov	QWORD PTR 32[rsp], 64
	lea	r9, 480[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	lea	r8, .LC32[rip]
	lea	rdi, 480[rsp]
	call	"optional_arg"
	test	eax, eax
	je	.L84
	test	r15b, r15b
	jne	.L151
	mov	ecx, 2
	mov	DWORD PTR 80[rsp], eax
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 62
	mov	edx, 1
	lea	rcx, .LC39[rip]
	mov	r9, rax
	call	"fwrite"
	mov	r11d, DWORD PTR 80[rsp]
	jmp	.L72
.L95:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 58
	mov	edx, 1
	lea	rcx, .LC40[rip]
	mov	r9, rax
	call	"fwrite"
	jmp	.L81
.L227:
	mov	eax, DWORD PTR 20140[rsp]
	mov	r9d, DWORD PTR 20132[rsp]
	lea	r8, .LC43[rip]
	mov	edx, 64
	lea	rcx, 352[rsp]
	mov	DWORD PTR 40[rsp], eax
	mov	eax, DWORD PTR 20136[rsp]
	mov	DWORD PTR 32[rsp], eax
	call	"snprintf"
	cmp	BYTE PTR 16032[rsp], 0
	jne	.L99
	xor	r8d, r8d
	mov	QWORD PTR 104[rsp], r8
	mov	QWORD PTR 96[rsp], r8
	mov	QWORD PTR 88[rsp], r8
.L100:
	mov	QWORD PTR 32[rsp], 256
	lea	r9, 544[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	lea	r8, .LC45[rip]
	call	"optional_arg"
	test	eax, eax
	je	.L228
.L101:
	mov	QWORD PTR 32[rsp], 256
	lea	r9, 800[rsp]
	mov	rdx, rbx
	mov	ecx, ebp
	lea	r8, .LC47[rip]
	call	"optional_arg"
	test	eax, eax
	je	.L229
.L102:
	cmp	BYTE PTR 544[rsp], 0
	je	.L230
.L103:
	cmp	BYTE PTR 800[rsp], 0
	je	.L231
.L104:
	call	"now_ms"
	mov	ecx, 4000000
	movapd	xmm7, xmm0
	call	"malloc"
	mov	r10, rax
	mov	eax, 1
	test	r10, r10
	je	.L232
.L105:
	mov	DWORD PTR -4[r10+rax*4], eax
	add	rax, 1
	cmp	rax, 1000001
	jne	.L105
	mov	QWORD PTR 80[rsp], r10
	call	"now_ms"
	xor	r11d, r11d
	test	r14d, r14d
	movzx	edx, BYTE PTR 16032[rsp]
	mov	r10, QWORD PTR 80[rsp]
	movapd	xmm6, xmm0
	jne	.L106
	test	dl, dl
	lea	rax, 2928[rsp]
	mov	rcx, r10
	cmove	rax, r11
	lea	r9, 1712[rsp]
	lea	r8, 168[rsp]
	lea	rdx, "function_call_sum"[rip]
	mov	r12, r9
	mov	QWORD PTR 40[rsp], rax
	lea	rax, 184[rsp]
	mov	QWORD PTR 32[rsp], rax
	call	"measure.constprop.0"
	mov	r10, QWORD PTR 80[rsp]
	test	eax, eax
	je	.L108
	xor	r11d, r11d
	lea	rax, 2112[rsp]
	cmp	BYTE PTR 16032[rsp], 0
	cmove	rax, r11
	lea	r9, 1312[rsp]
	lea	r8, 160[rsp]
	mov	r13, r9
	lea	rdx, "direct_sum"[rip]
	mov	QWORD PTR 40[rsp], rax
	lea	rax, 176[rsp]
	mov	QWORD PTR 32[rsp], rax
.L219:
	mov	rcx, r10
	call	"measure.constprop.0"
	mov	r10, QWORD PTR 80[rsp]
	test	eax, eax
	je	.L108
	mov	rcx, r13
	mov	QWORD PTR 80[rsp], r10
	lea	rdx, 3744[rsp]
	call	"sample_total"
	mov	rcx, r12
	movapd	xmm8, xmm0
	call	"sample_total"
	mov	ecx, 4096
	movapd	xmm9, xmm0
	call	[QWORD PTR __imp_GetCurrentDirectoryA[rip]]
	mov	r10, QWORD PTR 80[rsp]
	test	eax, eax
	je	.L233
	mov	QWORD PTR 80[rsp], r10
	test	r15b, r15b
	je	.L234
	lea	rdx, 11936[rsp]
	lea	rcx, 7840[rsp]
	mov	BYTE PTR 11936[rsp], r15b
	call	"strcpy"
	mov	r10, QWORD PTR 80[rsp]
	lea	r15, 7840[rsp]
.L116:
	xor	ecx, ecx
	mov	QWORD PTR 80[rsp], r10
	call	_time64
	lea	rdx, 208[rsp]
	lea	rcx, 416[rsp]
	mov	QWORD PTR 208[rsp], rax
	call	_localtime64_s
	lea	r9, 416[rsp]
	lea	r8, .LC58[rip]
	mov	edx, 32
	lea	rcx, 304[rsp]
	call	"strftime"
	lea	rcx, 20128[rsp]
	call	[QWORD PTR __imp_GetTimeZoneInformation[rip]]
	mov	ecx, DWORD PTR 20128[rsp]
	mov	r10, QWORD PTR 80[rsp]
	cmp	eax, 1
	je	.L235
	mov	edx, ecx
	add	ecx, DWORD PTR 20296[rsp]
	cmp	eax, 2
	cmovne	ecx, edx
.L118:
	mov	eax, ecx
	mov	r8d, 60
	mov	QWORD PTR 80[rsp], r10
	neg	eax
	lea	r9, 304[rsp]
	cmovs	eax, ecx
	cdq
	idiv	r8d
	test	ecx, ecx
	lea	r8, .LC59[rip]
	setg	cl
	movzx	ecx, cl
	lea	ecx, 43[rcx+rcx]
	mov	DWORD PTR 32[rsp], ecx
	lea	rcx, 256[rsp]
	mov	DWORD PTR 48[rsp], edx
	mov	edx, 48
	mov	DWORD PTR 40[rsp], eax
	call	"snprintf"
	xor	edx, edx
	xor	ecx, ecx
	xor	r8d, r8d
	lea	rax, 20128[rsp]
	mov	QWORD PTR 20128[rsp], rdx
	mov	r9d, 131097
	lea	rdx, .LC60[rip]
	mov	DWORD PTR 416[rsp], ecx
	mov	rcx, -2147483646
	mov	DWORD PTR 148[rsp], 256
	mov	BYTE PTR 1056[rsp], 0
	mov	QWORD PTR 32[rsp], rax
	call	[QWORD PTR __imp_RegOpenKeyExA[rip]]
	mov	r10, QWORD PTR 80[rsp]
	test	eax, eax
	je	.L236
.L120:
	mov	QWORD PTR 80[rsp], r10
	lea	rcx, 304[rsp]
	call	[QWORD PTR __imp_GetNativeSystemInfo[rip]]
	lea	rcx, 416[rsp]
	mov	DWORD PTR 416[rsp], 64
	call	[QWORD PTR __imp_GlobalMemoryStatusEx[rip]]
	mov	r10, QWORD PTR 80[rsp]
	test	eax, eax
	jne	.L121
	xor	eax, eax
	mov	QWORD PTR 424[rsp], rax
.L121:
	lea	rdx, .LC62[rip]
	mov	rcx, r15
	mov	QWORD PTR 80[rsp], r10
	call	"fopen"
	mov	rsi, rax
	test	rax, rax
	je	.L237
	lea	r8, .LC50[rip]
	lea	rdx, .LC64[rip]
	mov	rcx, rax
	call	"fprintf"
	lea	rdx, 544[rsp]
	mov	rcx, rsi
	lea	edi, -1[rbp]
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 14
	mov	edx, 1
	lea	rcx, .LC65[rip]
	call	"fwrite"
	lea	rdx, 800[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 37
	mov	edx, 1
	lea	rcx, .LC66[rip]
	call	"fwrite"
	lea	rdx, 256[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 196
	mov	edx, 1
	lea	rcx, .LC67[rip]
	call	"fwrite"
	lea	rdx, 3744[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 11
	mov	edx, 1
	lea	rcx, .LC68[rip]
	call	"fwrite"
	mov	DWORD PTR 24368[rsp], ebp
	mov	r15, QWORD PTR 80[rsp]
	mov	rbp, rbx
	xor	ebx, ebx
	jmp	.L124
.L238:
	mov	r9, rsi
	mov	edx, 1
	add	rbx, 1
	mov	r8d, 2
	lea	rcx, .LC69[rip]
	call	"fwrite"
	cmp	DWORD PTR 24368[rsp], ebx
	jle	.L123
.L124:
	mov	rdx, QWORD PTR 0[rbp+rbx*8]
	mov	rcx, rsi
	call	"write_json_string"
	cmp	rdi, rbx
	jne	.L238
.L123:
	mov	r9, rsi
	mov	edx, 1
	mov	QWORD PTR 80[rsp], r15
	mov	rbx, rbp
	mov	r8d, 25
	lea	rcx, .LC70[rip]
	call	"fwrite"
	test	r14d, r14d
	mov	r10, QWORD PTR 80[rsp]
	jne	.L239
	lea	rdx, .LC17[rip]
	mov	rcx, rsi
	mov	QWORD PTR 120[rsp], r10
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	lea	rcx, .LC69[rip]
	call	"fwrite"
	lea	rax, .LC17[rip]
	mov	r10, QWORD PTR 120[rsp]
	mov	QWORD PTR 112[rsp], rax
	mov	r14, rax
	lea	rax, .LC16[rip]
	mov	QWORD PTR 80[rsp], rax
	mov	r15, rax
.L150:
	mov	rdx, r15
	mov	rcx, rsi
	mov	QWORD PTR 120[rsp], r10
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 53
	mov	edx, 1
	lea	rcx, .LC71[rip]
	call	"fwrite"
	lea	rdx, 352[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 18
	mov	edx, 1
	lea	rcx, .LC72[rip]
	call	"fwrite"
	movzx	eax, WORD PTR 304[rsp]
	mov	r10, QWORD PTR 120[rsp]
	cmp	ax, 9
	je	.L159
	ja	.L128
	test	ax, ax
	je	.L160
	lea	rdx, .LC19[rip]
	cmp	ax, 5
	jne	.L129
.L127:
	mov	rcx, rsi
	mov	QWORD PTR 120[rsp], r10
	call	"write_json_string"
	mov	r10, QWORD PTR 120[rsp]
.L130:
	mov	r9, rsi
	mov	r8d, 9
	mov	edx, 1
	mov	QWORD PTR 120[rsp], r10
	lea	rcx, .LC74[rip]
	call	"fwrite"
	cmp	BYTE PTR 1056[rsp], 0
	je	.L131
	lea	rdx, 1056[rsp]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r10, QWORD PTR 120[rsp]
.L132:
	mov	r8d, DWORD PTR 336[rsp]
	lea	rdx, .LC75[rip]
	mov	rcx, rsi
	mov	QWORD PTR 120[rsp], r10
	call	"fprintf"
	mov	r8, QWORD PTR 424[rsp]
	test	r8, r8
	je	.L133
	lea	rdx, .LC76[rip]
	mov	rcx, rsi
	call	"fprintf"
	mov	r10, QWORD PTR 120[rsp]
.L134:
	mov	r9, rsi
	mov	r8d, 72
	mov	edx, 1
	mov	QWORD PTR 120[rsp], r10
	lea	rcx, .LC77[rip]
	call	"fwrite"
	mov	rdx, QWORD PTR 16[rbx]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 21
	mov	edx, 1
	lea	rcx, .LC78[rip]
	call	"fwrite"
	mov	rdx, QWORD PTR 24[rbx]
	mov	rcx, rsi
	call	"write_json_string"
	lea	rdx, .LC79[rip]
	mov	rcx, rsi
	movsd	xmm2, QWORD PTR 152[rsp]
	movq	r8, xmm2
	call	"fprintf"
	mov	rdx, QWORD PTR 32[rbx]
	mov	rcx, rsi
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 30
	mov	edx, 1
	lea	rcx, .LC80[rip]
	call	"fwrite"
	mov	rcx, QWORD PTR 40[rbx]
	lea	rdx, .LC81[rip]
	call	"fopen"
	mov	r10, QWORD PTR 120[rsp]
	test	rax, rax
	mov	rbp, rax
	je	.L135
	mov	rdi, r10
	jmp	.L136
.L137:
	mov	r9, rsi
	mov	r8, rbx
	mov	edx, 1
	lea	rcx, 20128[rsp]
	call	"fwrite"
	cmp	rbx, rax
	jne	.L240
.L136:
	mov	r9, rbp
	mov	r8d, 4096
	mov	edx, 1
	lea	rcx, 20128[rsp]
	call	"fread"
	mov	rbx, rax
	test	rax, rax
	jne	.L137
	mov	rcx, rbp
	mov	QWORD PTR 120[rsp], rdi
	call	"ferror"
	mov	r10, QWORD PTR 120[rsp]
	test	eax, eax
	jne	.L241
	movapd	xmm0, xmm6
	pxor	xmm3, xmm3
	pxor	xmm4, xmm4
	mov	rcx, rbp
	subsd	xmm0, xmm7
	movsd	xmm6, QWORD PTR .LC1[rip]
	movsd	xmm2, QWORD PTR .LC2[rip]
	mov	QWORD PTR 136[rsp], r10
	mulsd	xmm0, xmm6
	addsd	xmm0, xmm2
	cvttsd2si	rax, xmm0
	movapd	xmm0, xmm8
	addsd	xmm0, xmm9
	mulsd	xmm0, xmm6
	cvtsi2sd	xmm3, rax
	divsd	xmm3, xmm6
	addsd	xmm0, xmm2
	cvttsd2si	rax, xmm0
	cvtsi2sd	xmm4, rax
	divsd	xmm4, xmm6
	movsd	QWORD PTR 128[rsp], xmm3
	movsd	QWORD PTR 120[rsp], xmm4
	call	"fclose"
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	lea	rcx, .LC82[rip]
	call	"fwrite"
	movsd	xmm4, QWORD PTR 120[rsp]
	mov	rcx, rsi
	movsd	xmm1, QWORD PTR 160[rsp]
	movsd	xmm3, QWORD PTR 128[rsp]
	movsd	xmm2, QWORD PTR .LC2[rip]
	mov	DWORD PTR 32[rsp], 50
	mov	r9d, 5
	movapd	xmm0, xmm1
	movsd	QWORD PTR 56[rsp], xmm4
	movsd	xmm5, QWORD PTR 168[rsp]
	mov	r8d, 1000000
	addsd	xmm0, xmm3
	movsd	QWORD PTR 40[rsp], xmm3
	lea	rdx, .LC83[rip]
	addsd	xmm1, xmm5
	addsd	xmm0, xmm5
	mulsd	xmm1, xmm6
	addsd	xmm0, xmm4
	mulsd	xmm0, xmm6
	addsd	xmm1, xmm2
	addsd	xmm0, xmm2
	cvttsd2si	rax, xmm0
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, rax
	divsd	xmm0, xmm6
	cvttsd2si	rax, xmm1
	movsd	QWORD PTR 64[rsp], xmm0
	pxor	xmm0, xmm0
	cvtsi2sd	xmm0, rax
	divsd	xmm0, xmm6
	movsd	QWORD PTR 48[rsp], xmm0
	call	"fprintf"
	mov	rdx, r13
	mov	rcx, rsi
	call	"write_case"
	mov	r9, rsi
	mov	r8d, 19
	mov	edx, 1
	lea	rcx, .LC84[rip]
	call	"fwrite"
	mov	rdx, r12
	mov	rcx, rsi
	call	"write_case"
	mov	r9, QWORD PTR 184[rsp]
	mov	r8, QWORD PTR 176[rsp]
	mov	rcx, rsi
	movabs	rax, 500000500000
	lea	rdx, .LC85[rip]
	mov	QWORD PTR 32[rsp], rax
	call	"fprintf"
	mov	rcx, rsi
	call	"ferror"
	mov	rcx, rsi
	mov	ebx, eax
	call	"fclose"
	mov	r10, QWORD PTR 136[rsp]
	or	eax, ebx
	je	.L242
	mov	rcx, r10
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 58
	mov	edx, 1
	lea	rcx, .LC87[rip]
	mov	r9, rax
	call	"fwrite"
	jmp	.L81
.L87:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8, rdi
	lea	rdx, .LC34[rip]
	mov	rcx, rax
	call	"fprintf"
	jmp	.L81
.L222:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 59
	mov	edx, 1
	lea	rcx, .LC31[rip]
	mov	r9, rax
	call	"fwrite"
	jmp	.L81
.L223:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 55
	mov	edx, 1
	lea	rcx, .LC33[rip]
	mov	r9, rax
	call	"fwrite"
	jmp	.L81
.L108:
	mov	rcx, r10
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 39
	mov	edx, 1
	lea	rcx, .LC54[rip]
	mov	r9, rax
	call	"fwrite"
	jmp	.L81
.L106:
	test	dl, dl
	lea	rax, 2112[rsp]
	mov	rcx, r10
	mov	QWORD PTR 80[rsp], r10
	cmove	rax, r11
	lea	r9, 1312[rsp]
	lea	r8, 160[rsp]
	lea	rdx, "direct_sum"[rip]
	mov	r13, r9
	mov	QWORD PTR 40[rsp], rax
	lea	rax, 176[rsp]
	mov	QWORD PTR 32[rsp], rax
	call	"measure.constprop.0"
	mov	r10, QWORD PTR 80[rsp]
	test	eax, eax
	je	.L108
	xor	r11d, r11d
	lea	rax, 2928[rsp]
	cmp	BYTE PTR 16032[rsp], 0
	cmove	rax, r11
	lea	r9, 1712[rsp]
	lea	r8, 168[rsp]
	mov	r12, r9
	lea	rdx, "function_call_sum"[rip]
	mov	QWORD PTR 40[rsp], rax
	lea	rax, 184[rsp]
	mov	QWORD PTR 32[rsp], rax
	jmp	.L219
.L221:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 47
	mov	edx, 1
	lea	rcx, .LC27[rip]
	mov	r9, rax
	call	"fwrite"
	jmp	.L81
.L99:
	mov	rdx, QWORD PTR __imp_QueryPerformanceCounter[rip]
	lea	rcx, 20128[rsp]
	mov	QWORD PTR 80[rsp], rdx
	call	rdx
	mov	rax, QWORD PTR 20128[rsp]
	lea	rcx, 20128[rsp]
	mov	QWORD PTR 96[rsp], rax
	call	[QWORD PTR __imp_GetSystemTimePreciseAsFileTime[rip]]
	mov	rax, QWORD PTR 20128[rsp]
	lea	rcx, 20128[rsp]
	mov	QWORD PTR 88[rsp], rax
	call	[QWORD PTR 80[rsp]]
	mov	rax, QWORD PTR 20128[rsp]
	mov	QWORD PTR 104[rsp], rax
	jmp	.L100
.L231:
	lea	rcx, 20128[rsp]
	call	"timestamp_id.constprop.0"
	lea	rax, .LC50[rip]
	mov	edx, 256
	lea	r9, 20128[rsp]
	mov	QWORD PTR 40[rsp], rax
	lea	rax, .LC52[rip]
	lea	r8, .LC51[rip]
	mov	QWORD PTR 32[rsp], rax
	lea	rcx, 800[rsp]
	call	"snprintf"
	jmp	.L104
.L230:
	lea	rcx, 20128[rsp]
	call	"timestamp_id.constprop.0"
	lea	rax, .LC50[rip]
	mov	edx, 256
	lea	r9, 20128[rsp]
	mov	QWORD PTR 32[rsp], rax
	lea	r8, .LC49[rip]
	lea	rcx, 544[rsp]
	call	"snprintf"
	jmp	.L103
.L229:
	lea	rcx, .LC48[rip]
	call	"getenv"
	test	rax, rax
	je	.L102
	mov	r8d, 255
	mov	rdx, rax
	lea	rcx, 800[rsp]
	call	"strncpy"
	jmp	.L102
.L228:
	lea	rcx, .LC46[rip]
	call	"getenv"
	test	rax, rax
	je	.L101
	mov	r8d, 255
	mov	rdx, rax
	lea	rcx, 544[rsp]
	call	"strncpy"
	jmp	.L101
.L234:
	lea	rcx, 3744[rsp]
	call	"strlen"
	mov	r10, QWORD PTR 80[rsp]
	mov	r8, rax
	lea	rax, 49[rax]
	cmp	rax, 4096
	ja	.L243
	lea	rcx, 7840[rsp]
	lea	rdx, 3744[rsp]
	mov	QWORD PTR 112[rsp], r10
	mov	QWORD PTR 80[rsp], r8
	lea	rsi, .LC57[rip]
	lea	r15, 7840[rsp]
	call	"memcpy"
	mov	r8, QWORD PTR 80[rsp]
	mov	ecx, DWORD PTR .LC57[rip+44]
	lea	rdi, 7841[rsp+r8]
	mov	DWORD PTR 7885[rsp+r8], ecx
	mov	ecx, 11
	mov	BYTE PTR 7840[rsp+r8], 92
	rep movsd
	mov	r10, QWORD PTR 112[rsp]
	jmp	.L116
.L133:
	mov	r9, rsi
	mov	r8d, 4
	mov	edx, 1
	lea	rcx, .LC73[rip]
	call	"fwrite"
	mov	r10, QWORD PTR 120[rsp]
	jmp	.L134
.L239:
	lea	rdx, .LC16[rip]
	mov	rcx, rsi
	mov	QWORD PTR 120[rsp], r10
	call	"write_json_string"
	mov	r9, rsi
	mov	r8d, 2
	mov	edx, 1
	lea	rcx, .LC69[rip]
	call	"fwrite"
	lea	rax, .LC16[rip]
	mov	r10, QWORD PTR 120[rsp]
	mov	QWORD PTR 80[rsp], rax
	mov	r14, rax
	lea	rax, .LC17[rip]
	mov	QWORD PTR 112[rsp], rax
	mov	r15, rax
	jmp	.L150
.L131:
	mov	r9, rsi
	mov	r8d, 4
	mov	edx, 1
	lea	rcx, .LC73[rip]
	call	"fwrite"
	mov	r10, QWORD PTR 120[rsp]
	jmp	.L132
.L236:
	lea	rax, 148[rsp]
	mov	rcx, QWORD PTR 20128[rsp]
	xor	r8d, r8d
	lea	r9, 416[rsp]
	mov	QWORD PTR 40[rsp], rax
	lea	rax, 1056[rsp]
	lea	rdx, .LC61[rip]
	mov	QWORD PTR 32[rsp], rax
	call	[QWORD PTR __imp_RegQueryValueExA[rip]]
	mov	rcx, QWORD PTR 20128[rsp]
	call	[QWORD PTR __imp_RegCloseKey[rip]]
	mov	r10, QWORD PTR 80[rsp]
	jmp	.L120
.L235:
	add	ecx, DWORD PTR 20212[rsp]
	jmp	.L118
.L240:
	mov	rcx, rbp
	mov	QWORD PTR 80[rsp], rdi
	call	"fclose"
	mov	r10, QWORD PTR 80[rsp]
.L135:
	mov	rcx, rsi
	mov	QWORD PTR 80[rsp], r10
	call	"fclose"
	mov	rcx, QWORD PTR 80[rsp]
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 63
	mov	edx, 1
	lea	rcx, .LC86[rip]
	mov	r9, rax
	call	"fwrite"
	jmp	.L81
.L233:
	mov	rcx, r10
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 39
	mov	edx, 1
	lea	rcx, .LC55[rip]
	mov	r9, rax
	call	"fwrite"
	jmp	.L81
.L225:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, esi
	lea	rdx, .LC36[rip]
	mov	rcx, rax
	call	"fprintf"
	jmp	.L81
.L128:
	lea	rdx, .LC21[rip]
	cmp	ax, 12
	je	.L127
.L129:
	mov	r9, rsi
	mov	r8d, 4
	mov	edx, 1
	mov	QWORD PTR 120[rsp], r10
	lea	rcx, .LC73[rip]
	call	"fwrite"
	mov	r10, QWORD PTR 120[rsp]
	jmp	.L130
.L242:
	mov	rcx, r10
	mov	DWORD PTR 120[rsp], eax
	call	"free"
	cmp	BYTE PTR 16032[rsp], 0
	mov	r11d, DWORD PTR 120[rsp]
	je	.L141
	lea	rax, 2112[rsp]
	lea	rcx, 16032[rsp]
	mov	QWORD PTR 208[rsp], r13
	mov	QWORD PTR 192[rsp], rax
	lea	rax, 2928[rsp]
	lea	rdx, .LC62[rip]
	mov	QWORD PTR 200[rsp], rax
	mov	rax, QWORD PTR 80[rsp]
	mov	QWORD PTR 216[rsp], r12
	mov	QWORD PTR 20128[rsp], rax
	mov	rax, QWORD PTR 112[rsp]
	mov	QWORD PTR 20136[rsp], rax
	call	"fopen"
	mov	rcx, rax
	mov	rdi, rax
	test	rax, rax
	je	.L143
	mov	rax, QWORD PTR 104[rsp]
	mov	r9, QWORD PTR 88[rsp]
	mov	QWORD PTR 56[rsp], r15
	lea	rdx, .LC88[rip]
	mov	QWORD PTR 48[rsp], r14
	mov	r8, QWORD PTR "timer_frequency"[rip]
	mov	QWORD PTR 40[rsp], rax
	mov	rax, QWORD PTR 96[rsp]
	mov	QWORD PTR 32[rsp], rax
	call	"fprintf"
	mov	esi, DWORD PTR 120[rsp]
	xor	r10d, r10d
.L148:
	mov	rbx, QWORD PTR 192[rsp+r10*8]
	test	r10, r10
	mov	rcx, rdi
	mov	r9, QWORD PTR 20128[rsp+r10*8]
	lea	r8, .LC10[rip]
	mov	QWORD PTR 80[rsp], r10
	mov	rdx, QWORD PTR 808[rbx]
	mov	rax, QWORD PTR 800[rbx]
	mov	QWORD PTR 40[rsp], rdx
	lea	rdx, .LC89[rip]
	mov	QWORD PTR 32[rsp], rax
	lea	rax, .LC14[rip]
	cmove	r8, rax
	xor	ebp, ebp
	call	"fprintf"
	mov	r10, QWORD PTR 80[rsp]
.L147:
	mov	rax, QWORD PTR 208[rsp+r10*8]
	mov	rdx, QWORD PTR 8[rbx]
	mov	QWORD PTR 80[rsp], r10
	lea	r9d, 1[rbp]
	movsd	xmm0, QWORD PTR [rax+rbp*8]
	mov	rax, QWORD PTR [rbx]
	mov	QWORD PTR 40[rsp], rdx
	mov	QWORD PTR 32[rsp], rax
	movsd	QWORD PTR 48[rsp], xmm0
	test	ebp, ebp
	je	.L145
	lea	r8, .LC10[rip]
	lea	rdx, .LC90[rip]
	mov	rcx, rdi
	add	rbp, 1
	call	"fprintf"
	cmp	rbp, 50
	mov	r10, QWORD PTR 80[rsp]
	je	.L146
	add	rbx, 16
	jmp	.L147
.L145:
	mov	r9d, 1
	mov	rcx, rdi
	add	rbp, 1
	add	rbx, 16
	lea	r8, .LC14[rip]
	lea	rdx, .LC90[rip]
	call	"fprintf"
	mov	r10, QWORD PTR 80[rsp]
	jmp	.L147
.L244:
	test	ebp, ebp
	mov	r11d, DWORD PTR 80[rsp]
	jne	.L143
.L141:
	lea	rcx, .LC94[rip]
	mov	DWORD PTR 80[rsp], r11d
	call	"puts"
	mov	r11d, DWORD PTR 80[rsp]
	jmp	.L72
.L146:
	mov	r9, rdi
	mov	r8d, 2
	mov	edx, 1
	mov	QWORD PTR 80[rsp], r10
	lea	rcx, .LC91[rip]
	call	"fwrite"
	cmp	QWORD PTR 80[rsp], 1
	jne	.L164
	mov	r9, rdi
	mov	edx, 1
	mov	DWORD PTR 80[rsp], esi
	mov	r8d, 3
	lea	rcx, .LC92[rip]
	call	"fwrite"
	mov	rcx, rdi
	call	"ferror"
	mov	rcx, rdi
	mov	ebp, eax
	call	"fclose"
	test	eax, eax
	je	.L244
.L143:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 54
	mov	edx, 1
	lea	rcx, .LC93[rip]
	mov	r9, rax
	call	"fwrite"
	jmp	.L81
.L159:
	lea	rdx, .LC18[rip]
	jmp	.L127
.L226:
	call	[QWORD PTR __imp_GetLastError[rip]]
	mov	ecx, 2
	mov	ebx, eax
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r9d, ebx
	mov	r8d, esi
	lea	rdx, .LC37[rip]
	mov	rcx, rax
	call	"fprintf"
	jmp	.L81
.L224:
	call	[QWORD PTR __imp_GetLastError[rip]]
	mov	ecx, 2
	mov	ebx, eax
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, ebx
	lea	rdx, .LC35[rip]
	mov	rcx, rax
	call	"fprintf"
	jmp	.L81
.L160:
	lea	rdx, .LC20[rip]
	jmp	.L127
.L237:
	mov	rcx, QWORD PTR 80[rsp]
	call	"free"
	call	[QWORD PTR __imp__errno[rip]]
	mov	ecx, DWORD PTR [rax]
	call	[QWORD PTR __imp_strerror[rip]]
	mov	ecx, 2
	mov	rbx, rax
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8, rbx
	lea	rdx, .LC63[rip]
	mov	rcx, rax
	call	"fprintf"
	jmp	.L81
.L243:
	mov	rcx, r10
	call	"free"
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 45
	mov	edx, 1
	lea	rcx, .LC56[rip]
	mov	r9, rax
	call	"fwrite"
	jmp	.L81
.L241:
	mov	rcx, rbp
	mov	QWORD PTR 80[rsp], r10
	call	"fclose"
	mov	r10, QWORD PTR 80[rsp]
	jmp	.L135
.L164:
	mov	r10d, 1
	jmp	.L148
.L232:
	mov	ecx, 2
	call	[QWORD PTR __imp___acrt_iob_func[rip]]
	mov	r8d, 46
	mov	edx, 1
	lea	rcx, .LC53[rip]
	mov	r9, rax
	call	"fwrite"
	jmp	.L81
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
	.def	"strtoul";	.scl	2;	.type	32;	.endef
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

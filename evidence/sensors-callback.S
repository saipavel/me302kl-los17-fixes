
    push.w {r4, r5, r6, r7, r8, lr}
    sub sp, #0x80
    ldr r4, table_delta
table_pc:
    add r4, pc
    movs r5, #52
    movs r6, #0
    movs r7, #0
next_id:
    ldrh r0, [r4, #-2]!
    blx 0x6028
    rsbs r0, r0, #0
    adcs r6, r6
    adcs r7, r7
    subs r5, #1
    bne next_id
    movs r0, #1
    movs r1, #8
    bl 0xaac0
    cbz r0, cleanup
    mov r4, r0
    strd r6, r7, [r0]
    movw r0, #0x0300
    mov.w r1, #0x08000000
    movw r2, #2
    movt r2, #8
    str r0, [sp]
    str r1, [sp, #4]
    str r2, [sp, #8]
    mov r0, sp
    mov r1, r4
    bl 0xaccc
    cbnz r0, release_message
    mov r0, r4
    bl 0xaa60
    cbz r0, cleanup
release_message:
    mov r0, r4
    bl 0xab7c
cleanup:
    ldr r0, timer_delta
timer_pc:
    add r0, pc
    ldr r0, [r0]
    bl 0x704c
    add sp, #0x80
    pop.w {r4, r5, r6, r7, r8, pc}
    .balign 4
table_delta:
    .word 0x1d9d4
timer_delta:
    .word 0x26386

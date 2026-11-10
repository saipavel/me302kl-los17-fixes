
    ldr r6, [r5]
    ldr.w r8, [r5, #4]
    mov r5, r7
    mov.w r9, #2
next_name:
    cmp r6, r8
    bhs finished
    ldrb r2, [r6]
    ands r1, r2, #1
    ite eq
    lsreq r2, r2, #1
    ldrne r2, [r6, #4]
    cbz r2, skip_name
    cmp r1, #0
    ite eq
    addeq r1, r6, #1
    ldrne r1, [r6, #8]
    mov r0, r5
    movs r2, #35
    movs r3, #36
    blx 0x2dd720
skip_name:
    adds r6, #12
    adds r5, #36
    subs.w r9, r9, #1
    bne next_name
finished:
    b 0xc1d84
